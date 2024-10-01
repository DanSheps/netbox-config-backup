import logging
import time
import uuid
from datetime import timedelta
from multiprocessing import Process

from django.db.models import Q
from django.utils import timezone

from core.choices import JobStatusChoices
from netbox.jobs import JobRunner
from netbox_config_backup.backup.processing import run_backup
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models import Backup, BackupJob

logger = logging.getLogger(f"netbox_config_backup")


class BackupRunner(JobRunner):
    processes = {}

    class Meta:
        name = 'The Backup Job Runner'

    def clean_stale_jobs(self, old):
        for job in old.all():
            if job.pid:
                pass
            job.status = JobStatusChoices.STATUS_ERRORED
            if not job.data:
                job.data = {}
            job.data.update({'error': 'Job hung'})
            job.save()
            logger.warning(f'Job {job.backup} appears stuck, deleting')

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

    def fork_process(self, backup, job):
        process = Process(target=run_backup, args=(backup, job), )
        data = {
            backup.pk: {
                'process': process,
                'backup': backup.pk,
                'job': job.pk
            }
        }
        self.processes.update(data)
        process.start()
        logger.debug(f'Forking process {process.pid} for {backup.device} backup')
        return process

    def run(self, *args, **kwargs):
        try:
            running = BackupJob.objects.filter(
                ~Q(
                    status__in=[
                        JobStatusChoices.STATUS_COMPLETED,
                        JobStatusChoices.STATUS_ERRORED,
                        JobStatusChoices.STATUS_FAILED
                    ]
                )
            )
            old = running.filter(scheduled__lt=timezone.now() - timedelta(minutes=30))
            self.clean_stale_jobs(old)
            for backup in Backup.objects.filter(status=StatusChoices.STATUS_ACTIVE, device__isnull=False):
                logger.debug(f'Queuing device {backup.device} for backup')
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
                if backup.device and (backup.ip or backup.device.primary_ip):
                    process = self.fork_process(backup, job)
                    process.join(1)
                else:
                    job.status = JobStatusChoices.STATUS_FAILED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': f'Cannot backup {backup} due to no device or IPs'})
                    job.save()
                    logger.warning(f'Cannot backup {backup} due to no device or IPs')

            while(True):
                self.handle_processes()
                if len(self.processes) == 0:
                    return
                time.sleep(1)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            raise e
