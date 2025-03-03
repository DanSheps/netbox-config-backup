import logging
import time
import uuid
import traceback
from datetime import timedelta
from multiprocessing import Process

from django.utils import timezone

from core.choices import JobStatusChoices, JobIntervalChoices
from netbox import settings
from netbox.jobs import JobRunner, system_job
from netbox_config_backup.backup.processing import run_backup
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.utils.db import close_db
from netbox_config_backup.utils.rq import can_backup

logger = logging.getLogger(f"netbox_config_backup")


@system_job(interval=JobIntervalChoices.INTERVAL_MINUTELY)
class BackupRunner(JobRunner):
    processes = {}

    class Meta:
        name = 'The Backup Job Runner'

    @classmethod
    def fail_job(cls, job: BackupJob, status: str, error: str = ''):
        job.status = status
        if not job.data:
            job.data = {}
        job.data.update({'error': 'Process terminated'})
        job.save()
        job.refresh_from_db()


    @classmethod
    def clean_stale_jobs(cls):
        results = {
            'stale': 0,
            'scheduled': 0
        }

        jobs = BackupJob.objects.order_by('created').filter(
            status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES,
        ).prefetch_related('backup', 'backup__device')

        stale = jobs.filter(scheduled__lt=timezone.now() - timedelta(minutes=30))
        for job in stale:
            results['stale'] += 1
            cls.fail_job(job, JobStatusChoices.STATUS_FAILED, 'Job hung')
            logger.warning(f'Job {job.backup} appears stuck, deleting')

        scheduled = jobs.filter(status=JobStatusChoices.STATUS_SCHEDULED)
        for job in scheduled:
            if job != scheduled.filter(backup=job.backup).last():
                results['scheduled'] += 1
                cls.fail_job(job, JobStatusChoices.STATUS_ERRORED, 'Job missed')
                logger.warning(f'Job {job.backup} appears to have been missed, deleting')

        return results

    @classmethod
    def schedule_jobs(cls, runner, backup=None, device=None):
        scheduled_status = 0
        if backup:
            logging.debug(f'Scheduling backup for backup: {backup}')
            backups = Backup.objects.filter(pk=backup.pk, status=StatusChoices.STATUS_ACTIVE, device__isnull=False)
        elif device:
            logging.debug(f'Scheduling backup for device: {device}')
            backups = Backup.objects.filter(device=device, status=StatusChoices.STATUS_ACTIVE, device__isnull=False)
        else:
            logging.debug(f'Scheduling all backups')
            backups = Backup.objects.filter(status=StatusChoices.STATUS_ACTIVE, device__isnull=False)

        frequency = timedelta(seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency', 3600))

        for backup in backups:
            if can_backup(backup):
                logger.debug(f'Queuing device {backup.device} for backup')
                jobs = BackupJob.objects.filter(backup=backup)
                if jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES).count() == 0:
                    scheduled = timezone.now()
                    job = BackupJob(
                        runner=None,
                        backup=backup,
                        status=JobStatusChoices.STATUS_SCHEDULED,
                        scheduled=scheduled,
                        job_id=uuid.uuid4(),
                        data={},
                    )
                    job.full_clean()
                    job.save()
                    scheduled_status += 1
            else:
                jobs = BackupJob.objects.filter(backup=backup, status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
                for job in jobs:
                    cls.fail_job(job, JobStatusChoices.STATUS_FAILED, f'Cannot queue job')

        return scheduled_status

    def run_processes(self):
        jobs = BackupJob.objects.filter(
            runner=None,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled__lte=timezone.now()
        )
        for job in jobs:
            job.runner = self.job
            job.status = JobStatusChoices.STATUS_PENDING
            job.save()

        self.job.data.update({'status': {'pending': jobs.count()}})
        self.job.save()

        for job in jobs:
            try:
                process = self.fork_process(job)
                process.join(1)
            except Exception as e:
                job.status = JobStatusChoices.STATUS_FAILED
                job.data['error'] = str(e)
                job.save()

    def fork_process(self, job):
        close_db()
        process = Process(target=run_backup, args=(job.pk, ), )
        data = {
            job.backup.pk: {
                'process': process,
                'backup': job.backup.pk,
                'job': job.pk
            }
        }
        self.processes.update(data)
        process.start()
        logger.debug(f'Forking process {process.pid} for {job.backup} backup')
        return process

    def handle_processes(self):
        close_db()
        for pk in list(self.processes.keys()):
            terminated = self.job.data.get('status', {}).get('terminated', 0)
            completed = self.job.data.get('status', {}).get('completed', 0)

            process = self.processes.get(pk, {}).get('process')
            job_pk = self.processes.get(pk, {}).get('job')
            backup = self.processes.get(pk, {}).get('backup')
            if not process.is_alive():
                logger.debug(f'Terminating process {process.pid} with job pk of {pk} for {backup}')
                process.terminate()
                del self.processes[pk]
                job = BackupJob.objects.filter(pk=job_pk).first()
                if job and job.status != JobStatusChoices.STATUS_COMPLETED:
                    self.job.data.update({'status': {'terminated': terminated}})
                    job.status = JobStatusChoices.STATUS_ERRORED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': 'Process terminated'})
                    job.save()
                else:
                    self.job.data.update({'status': {'completed': completed}})
        self.job.save()
        self.job.refresh_from_db()

    def run(self, backup=None, device=None, *args, **kwargs):

        if not self.job.data:
            self.job.data = {}
            self.job.save()

        try:
            status = self.clean_stale_jobs()
            self.job.data.update({'status': status})

            status = self.schedule_jobs(runner=self.job, backup=backup, device=device)
            self.job.data.update({'status': {'scheduled': status}})

            self.job.save()

            self.run_processes()
            while(True):
                self.handle_processes()
                if len(self.processes) == 0:
                    return
                time.sleep(1)
        except Exception as e:
            logger.warning(f'{traceback.format_exc()}')
            logger.error(f'{e}')
            raise e
