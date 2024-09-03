import logging
import sys
import traceback
from datetime import timedelta

from django.utils import timezone
from django_rq import job
from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from core.choices import JobStatusChoices
from netbox import settings
from netbox.api.exceptions import ServiceUnavailable
from netbox.config import get_config
from netbox_config_backup.models import Backup, BackupJob, BackupCommit
from netbox_config_backup.utils.rq import can_backup


def get_logger():
    # Setup logging to Stdout
    formatter = logging.Formatter(f'[%(asctime)s][%(levelname)s] - %(message)s')
    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setLevel(logging.DEBUG)
    stdouthandler.setFormatter(formatter)
    logger = logging.getLogger(f"netbox_config_backup")
    logger.addHandler(stdouthandler)

    return logger


def napalm_init(device, ip=None, extra_args={}):
    from netbox import settings
    username = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get('NAPALM_USERNAME', None)
    password = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get('NAPALM_PASSWORD', None)
    timeout = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get('NAPALM_TIMEOUT', None)
    optional_args = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get('NAPALM_ARGS', []).copy()

    if device and device.platform and device.platform.napalm.napalm_args is not None:
        optional_args.update(device.platform.napalm.napalm_args)
    if extra_args != {}:
        optional_args.update(extra_args)

    # Check for primary IP address from NetBox object
    if ip is not None:
        host = str(ip.address.ip)
    elif device.primary_ip and device.primary_ip is not None:
        host = str(device.primary_ip.address.ip)
    else:
        raise ServiceUnavailable(
            "This device does not have a primary IP address"
        )

    # Check that NAPALM is installed
    try:
        import napalm
        from napalm.base.exceptions import ModuleImportError
    except ModuleNotFoundError as e:
        if getattr(e, 'name') == 'napalm':
            raise ServiceUnavailable("NAPALM is not installed. Please see the documentation for instructions.")
        raise e

    # Validate the configured driver
    try:
        driver = napalm.get_network_driver(device.platform.napalm.napalm_driver)
    except ModuleImportError:
        raise ServiceUnavailable("NAPALM driver for platform {} not found: {}.".format(
            device.platform, device.platform.napalm.napalm_driver
        ))

    # Connect to the device
    d = driver(
        hostname=host,
        username=username,
        password=password,
        timeout=timeout,
        optional_args=optional_args
    )
    try:
        d.open()
    except Exception as e:
        if isinstance(e, NetmikoAuthenticationException):
            logger.info('Authentication error')
        elif isinstance(e, NetmikoTimeoutException):
            logger.info('Connection error')
        raise ServiceUnavailable("Error connecting to the device at {}: {}".format(host, e))

    return d


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
        #logger.debug(f'[{pk}] Connecting')
        d = napalm_init(backup.device, ip)
        #logger.debug(f'[{pk}] Finished Connection')

        #logger.debug(f'[{pk}] Getting config')
        configs = d.get_config()
        #logger.debug(f'[{pk}] Finished config get')

        #logger.debug(f'[{pk}] Setting config')
        commit = backup.set_config(configs, pk=pk)
        #logger.debug(f'[{pk}] Finished config set')

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
    delay = timedelta(seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency'))

    job_result.started = timezone.now()
    job_result.status = JobStatusChoices.STATUS_RUNNING
    job_result.save()
    try:
        #logger.debug(f'[{pk}] Starting backup')
        commit = backup_config(backup, pk=pk)
        #logger.debug(f'[{pk}] Finished backup')

        job_result.set_status(JobStatusChoices.STATUS_COMPLETED)
        job_result.data = {'commit': f'{commit}' if commit is not None else ''}
        job_result.set_status(JobStatusChoices.STATUS_COMPLETED)
        # Enqueue next job if one doesn't exist
        try:
            #logger.debug(f'[{pk}] Starting Enqueue')
            BackupJob.objects.filter(
                backup=backup
            ).exclude(
                status__in=JobStatusChoices.TERMINAL_STATE_CHOICES
            ).update(status=JobStatusChoices.STATUS_FAILED)
            BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)
            #logger.debug(f'[{pk}] Finished Enqueue')
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

    #logger.debug(f'[{pk}] Saving result')
    job_result.save()


logger = get_logger()
