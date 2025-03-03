import logging
import os
import time
import traceback
from datetime import timedelta

import uuid
from django.db.models import Q
from django.utils import timezone

from core.choices import JobStatusChoices
from netbox import settings
from netbox.api.exceptions import ServiceUnavailable
from netbox_config_backup.models import BackupJob, Backup
from netbox_config_backup.utils.db import close_db
from netbox_config_backup.utils.configs import check_config_save_status
from netbox_config_backup.utils.napalm import napalm_init
from netbox_config_backup.utils.rq import can_backup

logger = logging.getLogger(f"netbox_config_backup")


def remove_stale_backupjobs(job: BackupJob):
    pass

def run_backup(job_id):
    close_db()
    logger.info(f'Starting backup for job {job_id}')
    try:
        job = BackupJob.objects.get(pk=job_id)
    except Exception as e:
        logger.error(f'Unable to load job {job_id}: {e}')
        logger.debug(f'\t{traceback.format_exc()}')
        raise e

    try:
        backup = Backup.objects.get(pk=job.backup.pk)
        backup.refresh_from_db()
        pid = os.getpid()

        job.status = JobStatusChoices.STATUS_PENDING
        job.pid = pid
        job.save()

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
        try:
            ip = backup.ip if backup.ip is not None else backup.device.primary_ip
        except Exception as e:
            logger.debug(f'{e}: {backup}')
            raise e

        if ip:
            try:
                d = napalm_init(backup.device, ip)
            except (TimeoutError, ServiceUnavailable):
                job.status = JobStatusChoices.STATUS_FAILED
                job.data = {'error': f'Timeout Connecting to {backup.device} with ip {ip}'}
                logger.debug = f'Timeout Connecting to {backup.device} with ip {ip}'
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

            frequency = timedelta(
                seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency', 3600)
            )
            new = BackupJob(
                runner=None,
                backup=job.backup,
                status=JobStatusChoices.STATUS_SCHEDULED,
                scheduled=timezone.now() + frequency,
                job_id=uuid.uuid4(),
                data={},
            )
            new.full_clean()
            new.save()

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
        logger.error(f'Exception in {job_id}: {e}')
        logger.info(f'\t{traceback.format_exc()}')
        if job:
            job.status = JobStatusChoices.STATUS_ERRORED
            if not job.data:
                job.data = {}
            job.data.update({'error': f'{e}'})
            job.full_clean()
            job.save()
