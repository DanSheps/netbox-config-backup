import logging
import os
import traceback

from django.db.models import Q
from django.utils import timezone

from core.choices import JobStatusChoices
from netbox.api.exceptions import ServiceUnavailable
from netbox_config_backup.models import BackupJob
from netbox_config_backup.utils.configs import check_config_save_status
from netbox_config_backup.utils.napalm import napalm_init
from netbox_config_backup.utils.rq import can_backup

logger = logging.getLogger(f"netbox_config_backup")


def remove_stale_backupjobs(job: BackupJob):
    BackupJob.objects.filter(backup=job.backup).exclude(status=JobStatusChoices.STATUS_COMPLETED).exclude(
        pk=job.pk).delete()

def run_backup(backup, job):
    pid = os.getpid()

    job.status = JobStatusChoices.STATUS_PENDING
    job.pid = pid
    job.save()
    try:
        if not can_backup(backup):
            job.status = JobStatusChoices.STATUS_FAILED
            if not job.data:
                job.data = {}
            job.data.update({'error': f'Cannot backup {backup}'})
            job.full_clean()
            job.save()
            logger.warning(f'Cannot backup {backup}')
            return

        commit = None
        ip = backup.ip if backup.ip is not None else backup.device.primary_ip

        if ip:
            try:
                d = napalm_init(backup.device, ip)
            except (TimeoutError, ServiceUnavailable):
                job.status = JobStatusChoices.STATUS_FAILED
                job.data = {'error': f'Timeout Connecting to {backup.device} with ip {ip}'}
                job.save()
                return

            job.status = JobStatusChoices.STATUS_RUNNING
            job.started = timezone.now()
            job.save()
            try:
                status = check_config_save_status(d)
                if status is not None:
                    if status and not backup.config_status:
                        backup.config_status = status
                        backup.save()
                    elif not status and backup.config_status:
                        backup.config_status = status
                        backup.save()
                    elif not status and backup.config_status is None:
                        backup.config_status = status
                        backup.save()
                    elif status and backup.config_status is None:
                        backup.config_status = status
                        backup.save()
            except Exception as e:
                logger.error(f'{backup}: had error setting backup status: {e}')

            configs = d.get_config()
            commit = backup.set_config(configs)

            d.close()
            logger.info(f'{backup}: Backup complete')
            job.status = JobStatusChoices.STATUS_COMPLETED
            job.completed = timezone.now()
            job.save()
            remove_stale_backupjobs(job=job)
        else:
            job.status = JobStatusChoices.STATUS_FAILED
            if not job.data:
                job.data = {}
            job.data.update({'error': f'{backup}: No IP set'})
            job.full_clean()
            job.save()
            logger.debug(f'{backup}: No IP set')
    except Exception as e:
        job.status = JobStatusChoices.STATUS_ERRORED
        if not job.data:
            job.data = {}
        job.data.update({'error': f'{e}'})
        job.full_clean()
        job.save()
        logger.error(f'Exception in {backup}: {e}')
        logger.info(f'{backup}: {traceback.format_exc()}')
