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
    class Meta:
        name = 'The Backup Job Runner'

    def run(self, *args, **kwargs):
        processes = {}
        for backup in Backup.objects.filter(status=StatusChoices.STATUS_ACTIVE, device__isnull=False):
            running = BackupJob.objects.filter(
                ~Q(
                    status__in=[
                        JobStatusChoices.STATUS_COMPLETED,
                        JobStatusChoices.STATUS_ERRORED,
                        JobStatusChoices.STATUS_FAILED
                    ]
                )
            )
            while running.count() >= 5:
                logger.debug(f'Number of running jobs >= 5, sleeping for 60 seconds')
                old = running.filter(scheduled__lt=timezone.now() - timedelta(minutes=30))
                for job in old.all():
                    if job.pid and processes.get(job.pid):
                        processes.get(job.pid).terminate()
                    job.status = JobStatusChoices.STATUS_ERRORED
                    if not job.data:
                        job.data = {}
                    job.data.update({'error': 'Job hung'})
                    job.delete()
                    logger.error(f'Job {job.backup} appears stuck, deleting')
                time.sleep(60)

            logger.info(f'Queuing device {backup.device} for backup')
            job = BackupJob(
                backup=backup,
                status=JobStatusChoices.STATUS_SCHEDULED,
                scheduled=timezone.now(),
                job_id=uuid.uuid4(),
                data={},
            )
            job.full_clean()
            job.save()
            if backup.device and (backup.ip or backup.device.primary_ip):
                process = Process(target=run_backup, args=(backup, job), )
                logger.info(f'Forking process {process.pid} for {backup.device} backup')
                processes.update({backup.pk: process})
                process.start()
                time.sleep(10)
            else:
                job.status=JobStatusChoices.STATUS_FAILED
                if not job.data:
                    job.data = {}
                job.data.update({'error': f'Cannot backup {backup} due to no device or IPs'})
                job.save()
                logger.warning(f'Cannot backup {backup} due to no device or IPs')

        while(True):
            for pk in list(processes.keys()):
                process = processes.get(pk)
                if not process.is_alive():
                    process.terminate()
                    del processes[pk]
            if len(processes) == 0:
                return
            time.sleep(1)
