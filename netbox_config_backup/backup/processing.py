import logging
import os
import traceback
from datetime import timedelta

import uuid
from django.utils import timezone

from core.choices import JobStatusChoices
from netbox import settings
from netbox.api.exceptions import ServiceUnavailable
from netbox_config_backup.models import BackupJob, Backup
from netbox_config_backup.utils.db import close_db
from netbox_config_backup.utils.configs import check_config_save_status
from netbox_config_backup.utils.napalm import napalm_init
from netbox_config_backup.utils.rq import can_backup

logger = logging.getLogger("netbox_config_backup")


def remove_stale_backupjobs(job: BackupJob):
    pass


def run_backup(job_id):
    close_db()
    logger.info(f'Starting backup for job {job_id}')
    try:
        logger.debug(f'Trying to load job {job_id}')
        job = BackupJob.objects.get(pk=job_id)
    except Exception as e:
        logger.error(f'Unable to load job {job_id}: {e}')
        logger.debug(f'\t{traceback.format_exc()}')
        raise e

    try:
        logger.debug(f'Getting backup for {job}')
        backup = Backup.objects.get(pk=job.backup.pk)
        backup.refresh_from_db()
        pid = os.getpid()

        logger.debug(f'Setting status and saving for {job}')

        job.status = JobStatusChoices.STATUS_PENDING
        job.pid = pid
        job.save()

        logger.debug(f'Checking backup status for {job}')
        if not can_backup(backup):
            logger.info(f'Cannot backup {backup}')
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
            logger.debug(
                f'Trying to connect to device {backup.device} with ip {ip} for {job}'
            )
            try:
                d = napalm_init(backup.device, ip)
            except (TimeoutError, ServiceUnavailable):
                job.status = JobStatusChoices.STATUS_FAILED
                job.data = {
                    'error': f'Timeout Connecting to {backup.device} with ip {ip}'
                }
                logger.debug(f'Timeout Connecting to {backup.device} with ip {ip}')
                job.save()
                return
            logger.debug(f'Connected to {backup.device} with ip {ip} for {job}')
            job.status = JobStatusChoices.STATUS_RUNNING
            job.started = timezone.now()
            job.save()
            try:
                logger.debug(f'Checking config save status for {backup}')
                config_save_status = check_config_save_status(d)
                status = config_save_status.get('status')
                running = backup.files.filter(type='running').first()
                startup = backup.files.filter(type='startup').first()
                if running.last_change != config_save_status.get('running', None):
                    running.last_change = config_save_status.get('running', None)
                    running.clean()
                    running.save()
                if startup.last_change != config_save_status.get('startup', None):
                    startup.last_change = config_save_status.get('startup', None)
                    startup.clean()
                    startup.save()

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

            logger.debug(f'Getting config for {backup}')
            configs = d.get_config()
            logger.debug(f'Committing config for {backup}')
            commit = backup.set_config(configs)
            logger.debug(
                f'Committed config for {backup} with {commit}; closing connection for {backup}'
            )
            d.close()

            logger.debug(f'Scheduling next backup for {backup}')
            frequency = timedelta(
                seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get(
                    'frequency', 3600
                )
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
            logger.debug(f'{backup}: No IP set')
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
