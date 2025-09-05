import logging
import signal
import time
import uuid
import traceback
import multiprocessing
from datetime import timedelta

import sentry_sdk
from django.utils import timezone

from core.choices import JobStatusChoices, JobIntervalChoices
from netbox import settings
from netbox.jobs import JobRunner, system_job
from netbox_config_backup.backup.processing import run_backup
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.exceptions import JobExit
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.utils.db import close_db
from netbox_config_backup.utils.rq import can_backup

__all__ = ('BackupRunner',)


logger = logging.getLogger("netbox_config_backup")

job_frequency = settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency', 3600)


@system_job(interval=JobIntervalChoices.INTERVAL_MINUTELY * 15)
class BackupRunner(JobRunner):
    processes = {}

    class Meta:
        name = 'Backup Job Runner'

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
        logger.info('Starting stale job cleanup')
        results = {'stale': 0, 'scheduled': 0}

        jobs = (
            BackupJob.objects.order_by('created')
            .filter(
                status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES,
            )
            .prefetch_related('backup', 'backup__device')
        )

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
            logging.debug('Scheduling all backups for')
            backups = Backup.objects.filter(status=StatusChoices.STATUS_ACTIVE, device__isnull=False)

        frequency = timedelta(seconds=job_frequency)

        for backup in backups:
            if can_backup(backup):
                logger.debug(f'Checking jobs for backup for {backup.device}' f'+')
                jobs = BackupJob.objects.filter(backup=backup)
                if jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES).count() == 0:
                    logger.debug(f'Queuing device {backup.device} for backup')
                    if jobs.last().scheduled + frequency < timezone.now():
                        scheduled = timezone.now()
                    else:
                        scheduled = jobs.last().scheduled + frequency
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
                    cls.fail_job(job, JobStatusChoices.STATUS_FAILED, 'Cannot queue job')

        return scheduled_status

    def run_processes(self):
        if not self.running:
            self.handle_main_exit(signal.SIGTERM, None)
        jobs = BackupJob.objects.filter(
            runner=None,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled__lte=timezone.now(),
        )
        for job in jobs:
            job.runner = self.job
            job.status = JobStatusChoices.STATUS_PENDING

        close_db()
        BackupJob.objects.bulk_update(jobs, ['runner', 'status'])

        self.job.data.update({'status': {'pending': jobs.count()}})
        self.job.clean()
        self.job.save()

        for job in jobs:
            try:
                process = self.fork_process(job)
                process.join(1)
                job.pid = process.pid
                job.status = JobStatusChoices.STATUS_RUNNING
            except Exception as e:
                sentry_sdk.capture_exception(e)
                job.status = JobStatusChoices.STATUS_FAILED
                job.data['error'] = str(e)

        close_db()
        BackupJob.objects.bulk_update(jobs, ['pid', 'status', 'data'])

    def run_backup(self, job_id):
        self.job_id = job_id
        if not self.running:
            self.handle_main_exit(signal.SIGTERM, None)
        signal.signal(signal.SIGTERM, self.handle_child_exit)
        signal.signal(signal.SIGINT, self.handle_child_exit)
        run_backup(job_id)

    def fork_process(self, job):
        if not self.running:
            return
        close_db()
        process = self.ctx.Process(
            target=run_backup,
            args=(job.pk,),
        )
        data = {job.backup.pk: {'process': process, 'backup': job.backup.pk, 'job': job.pk}}
        self.processes.update(data)
        process.start()
        logger.debug(f'Forking process {process.pid} for {job.backup} backup')
        return process

    def handle_stuck_jobs(self):
        jobs = BackupJob.objects.filter(
            status__in=['running', 'pending'],
            started__gte=timezone.now() + timedelta(seconds=job_frequency),
        )
        for job in jobs:
            if self.processes.get(job.backup.pk):
                process = self.processes.get(job.backup.pk)
                if process.is_alive():
                    process.terminate()
                del self.processes[job.backup.pk]
            job.status = JobStatusChoices.STATUS_ERRORED
            if not job.data:
                job.data = {}
            job.data.update({'error': 'Process terminated'})
        BackupJob.objects.bulk_update(jobs, ['status', 'data'])

    def handle_processes(self):
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
                if job and job.status not in [
                    JobStatusChoices.STATUS_COMPLETED,
                    JobStatusChoices.STATUS_FAILED,
                    JobStatusChoices.STATUS_ERRORED,
                ]:
                    self.job.data.update({'status': {'terminated': terminated}})
                    job.status = JobStatusChoices.STATUS_ERRORED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': 'Process terminated for unknown reason'})
                else:
                    self.job.data.update({'status': {'completed': completed}})
                job.save()

        self.job.save()
        self.job.refresh_from_db()

    def handle_main_exit(self, signum, frame):
        logger.info(f'Exiting Main: {signum}')
        self.handle_exit('Parent', signum)

    def handle_child_exit(self, signum, frame):
        logger.info(f'Exiting Child: {signum}')
        self.handle_exit('Child', signum)
        raise JobExit('Terminating')

    def handle_exit(self, process, signum):
        code = f'UNKNOWN: {signum}'
        match signum:
            case signal.SIGKILL:
                code = 'SIGKILL'
            case signal.SIGTERM:
                code = 'SIGTERM'
            case signal.SIGINT:
                code = 'SIGINT'
        logger.info(f'Exiting {process}: {code}')
        self.job.data.update({'status': {'terminated': 1}})
        if process != 'Child':
            self.running = False
            for pk in list(self.processes.keys()):
                process = self.processes.get(pk, {}).get('process')
                job_pk = self.processes.get(pk, {}).get('job')
                job = BackupJob.objects.filter(pk=job_pk).first()
                job.status = JobStatusChoices.STATUS_ERRORED
                job.data.update({'error': f'{process}: {code}'})
                job.clean()
                job.save()
                process.terminate()
                try:
                    process.join()
                except AssertionError:
                    pass

    def run(self, backup=None, device=None, *args, **kwargs):

        self.ctx = multiprocessing.get_context()
        self.running = True

        signal.signal(signal.SIGTERM, self.handle_main_exit)
        signal.signal(signal.SIGINT, self.handle_main_exit)

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

            self.handle_processes()
            self.handle_stuck_jobs()

            while self.running:
                self.handle_processes()
                self.handle_stuck_jobs()
                if len(self.processes) == 0:
                    self.running = False
                time.sleep(1)
        except JobExit as e:
            raise e
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.warning(f'{traceback.format_exc()}')
            logger.error(f'{e}')
            raise e
