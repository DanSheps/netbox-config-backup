import logging
import time
import uuid
import traceback
from datetime import timedelta
from multiprocessing import Process

from django.db.models import Q
from django.utils import timezone
from rq.job import JobStatus

from core.choices import JobStatusChoices
from netbox.jobs import JobRunner
from netbox_config_backup.backup.processing import run_backup
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.utils.rq import can_backup

logger = logging.getLogger(f"netbox_config_backup")


class SchedulerRunner(JobRunner):
    class Meta:
        name = "The scheduler"




class BackupRunner(JobRunner):
    processes = {}

    class Meta:
        name = 'The Backup Job Runner'

    def clean_stale_jobs(self):
        jobs = BackupJob.objects.order_by('created').filter(
            status=JobStatusChoices.ENQUEUED_STATE_CHOICES,
        ).prefetch_related('device')
        scheduled = jobs.filter(status=JobStatusChoices.STATUS_SCHEDULED)
        stale = jobs.filter(scheduled__lt=timezone.now() - timedelta(minutes=30))

        for job in stale:
            if job.pid:
                pass
            job.status = JobStatusChoices.STATUS_ERRORED
            if not job.data:
                job.data = {}
            job.data.update({'error': 'Job hung'})
            job.save()
            job.refresh_from_db()
            logger.warning(f'Job {job.backup} appears stuck, deleting')

        for job in scheduled:
            if job != scheduled.filter(backup=job.backup).last():
                job.status = JobStatusChoices.STATUS_FAILED
                if not job.data:
                    job.data = {}
                job.data.update({'error': 'Process terminated'})
                job.save()

    def schedule_jobs(self):
        backups = Backup.objects.filter(status=StatusChoices.STATUS_ACTIVE, device__isnull=False)
        for backup in backups:
            if can_backup(backup):
                logger.debug(f'Queuing device {backup.device} for backup')
                jobs = BackupJob.objects.filter(backup=backup, status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
                job = jobs.last()
                if job is not None:
                    job.runner = self.job
                    job.status = JobStatusChoices.STATUS_SCHEDULED
                    job.scheduled = timezone.now()
                    job.save()
                else:
                    job = BackupJob(
                        runner=self.job,
                        backup=backup,
                        status=JobStatusChoices.STATUS_SCHEDULED,
                        scheduled=timezone.now(),
                        job_id=uuid.uuid4(),
                        data={},
                    )
                job.full_clean()
                job.save()
            else:
                jobs = BackupJob.objects.filter(backup=backup, status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
                for job in jobs:
                    job.status = JobStatusChoices.STATUS_FAILED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': f'Cannot queue job'})
                    job.save()

    def run_processes(self):
        for job in BackupJob.objects.filter(status=JobStatusChoices.STATUS_SCHEDULED):
            job.refresh_from_db()
            try:
                process = self.fork_process(job)
                process.join(1)
            except Exception as e:
                job.status = JobStatusChoices.STATUS_FAILED
                job.data['error'] = str(e)
                job.save()

    def fork_process(self, job):
        backup = Backup.objects.get(pk=job.backup.pk)
        process = Process(target=run_backup, args=(job.pk, backup.pk), )
        data = {
            backup.pk: {
                'process': process,
                'backup': backup.pk,
                'job': job.pk
            }
        }
        self.processes.update(data)
        process.start()
        logger.debug(f'Forking process {process.pid} for {backup} backup')
        return process

    def handle_processes(self):
        for pk in list(self.processes.keys()):
            process = self.processes.get(pk, {}).get('process')
            job_pk = self.processes.get(pk, {}).get('job')
            backup = self.processes.get(pk, {}).get('backup')
            if not process.is_alive():
                logger.debug(f'Terminating process {process.pid} with job pk of {pk} for {backup}')
                process.terminate()
                del self.processes[pk]
                job = BackupJob.objects.filter(pk=job_pk).first()
                if job and job.status != JobStatusChoices.STATUS_COMPLETED:
                    job.status = JobStatusChoices.STATUS_ERRORED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': 'Process terminated'})
                    job.save()

    def run(self, *args, **kwargs):
        try:
            self.clean_stale_jobs()
            time.sleep(5)
            self.schedule_jobs()
            time.sleep(5)
            self.run_processes()
            while(True):
                self.handle_processes()
                if len(self.processes) == 0:
                    return
                time.sleep(1)
        except Exception as e:
            logger.warning(f'{traceback.format_exc()}')
            logger.error(f'{e}')
