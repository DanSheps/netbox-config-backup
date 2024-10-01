import traceback
from datetime import timedelta

from django.utils import timezone

from core.choices import JobStatusChoices
from netbox import settings
from netbox.api.exceptions import ServiceUnavailable
from netbox_config_backup.backup.processing import logger
from netbox_config_backup.models import BackupJob
from netbox_config_backup.utils.configs import check_config_save_status
from netbox_config_backup.utils.logger import get_logger
from netbox_config_backup.utils.napalm import napalm_init
from netbox_config_backup.utils.rq import can_backup


def backup_config(backup, pk=None):
    commit = None
    if backup.device:
        ip = backup.ip if backup.ip is not None else backup.device.primary_ip
    else:
        ip = None
    if not can_backup(backup):
        raise Exception(f'Cannot backup {backup}')

    if backup.device is not None and ip is not None:
        logger.info(f'{backup}: Backup started')
        # logger.debug(f'[{pk}] Connecting')
        d = napalm_init(backup.device, ip)
        # logger.debug(f'[{pk}

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

        # logger.debug(f'[{pk}] Getting config')
        configs = d.get_config()
        # logger.debug(f'[{pk}] Finished config get')

        # logger.debug(f'[{pk}] Setting config')
        commit = backup.set_config(configs, pk=pk)
        # logger.debug(f'[{pk}] Finished config set')

        d.close()
        logger.info(f'{backup}: Backup complete')
    else:
        logger.info(f'{backup}: No IP set')

    return commit


def backup_job(pk):
    import netmiko

    try:
        job_result = BackupJob.objects.get(pk=pk)
    except BackupJob.DoesNotExist:
        logger.error(f'Cannot locate job (Id: {pk}) in DB')
        raise Exception(f'Cannot locate job (Id: {pk}) in DB')
    backup = job_result.backup

    if not can_backup(backup):
        logger.warning(f'Cannot backup due to additional factors')
        return 1
    delay = timedelta(
        seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency')
    )

    job_result.started = timezone.now()
    job_result.status = JobStatusChoices.STATUS_RUNNING
    job_result.save()
    try:
        # logger.debug(f'[{pk}] Starting backup')
        commit = backup_config(backup, pk=pk)
        # logger.debug(f'[{pk}] Finished backup')

        job_result.set_status(JobStatusChoices.STATUS_COMPLETED)
        job_result.data = {'commit': f'{commit}' if commit is not None else ''}
        job_result.set_status(JobStatusChoices.STATUS_COMPLETED)
        # Enqueue next job if one doesn't exist
        try:
            # logger.debug(f'[{pk}] Starting Enqueue')
            BackupJob.objects.filter(backup=backup).exclude(
                status__in=JobStatusChoices.TERMINAL_STATE_CHOICES
            ).update(status=JobStatusChoices.STATUS_FAILED)
            BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)
            # logger.debug(f'[{pk}] Finished Enqueue')
        except Exception as e:
            logger.error(f'Job Enqueue after completion failed for job: {backup}')
            logger.error(f'\tException: {e}')
    except netmiko.exceptions.ReadTimeout as e:
        BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)
        logger.warning(f'Netmiko read timeout on job: {backup}')
    except ServiceUnavailable as e:
        logger.info(f'Napalm service read failure on job: {backup} ({e})')
        BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)
    except Exception as e:
        logger.error(f'Uncaught Exception on job: {backup}')
        logger.error(e)
        logger.warning(traceback.format_exc())
        job_result.set_status(JobStatusChoices.STATUS_ERRORED)
        BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)

    # logger.debug(f'[{pk}] Saving result')
    job_result.save()


logger = get_logger()
