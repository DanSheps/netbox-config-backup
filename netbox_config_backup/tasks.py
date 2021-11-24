import logging
import sys
import traceback
from datetime import timedelta

from django.utils import timezone
from django_rq import job

from extras.choices import JobResultStatusChoices
from netbox import settings
from netbox.api.exceptions import ServiceUnavailable
from netbox_config_backup.models import Backup, BackupJob, BackupCommit


def get_logger():
    # Setup logging to Stdout
    formatter = logging.Formatter(f'[%(asctime)s][%(levelname)s] - %(message)s')
    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setLevel(logging.DEBUG)
    stdouthandler.setFormatter(formatter)
    logger = logging.getLogger(f"netbox_config_backup")
    logger.addHandler(stdouthandler)

    return logger


def napalm_init(device, extra_args={}):
    username = settings.NAPALM_USERNAME
    password = settings.NAPALM_PASSWORD
    timeout = settings.NAPALM_TIMEOUT
    optional_args = settings.NAPALM_ARGS.copy()
    if device.platform.napalm_args is not None:
        optional_args.update(device.platform.napalm_args)
    if extra_args != {}:
        optional_args.update(extra_args)

    # Check for primary IP address from NetBox object
    if device.primary_ip:
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
        driver = napalm.get_network_driver(device.platform.napalm_driver)
    except ModuleImportError:
        raise ServiceUnavailable("NAPALM driver for platform {} not found: {}.".format(
            device.platform, device.platform.napalm_driver
        ))

    # Connect to the device
    d = driver(
        hostname=host,
        username=username,
        password=password,
        timeout=settings.NAPALM_TIMEOUT,
        optional_args=optional_args
    )
    try:
        d.open()
    except Exception as e:
        raise ServiceUnavailable("Error connecting to the device at {}: {}".format(host, e))

    return d


def backup_config(backup):
    commit = None
    if backup.device is not None and backup.device.primary_ip is not None:
        logger.info(f'{backup} backup started')
        d = napalm_init(backup.device)

        configs = d.get_config()

        commit = backup.set_config(configs)

        d.close()
        logger.info(f'{backup} backup complete')
    else:
        logger.info(f'{backup} no IP set')

    return commit


def backup_job(pk):
    try:
        job_result = BackupJob.objects.get(pk=pk)
    except BackupJob.DoesNotExist:
        raise Exception('Cannot locate job in DB')
    backup = job_result.backup
    delay = timedelta(seconds=settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency'))

    job_result.started = timezone.now()
    job_result.status = JobResultStatusChoices.STATUS_RUNNING
    job_result.save()
    try:
        commit = backup_config(backup)

        job_result.set_status(JobResultStatusChoices.STATUS_COMPLETED)
        job_result.data = {'commit': f'{commit}' if commit is not None else ''}

        # Enqueue next job if one doesn't exist
        try:
            BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)
        except Exception as e:
            logger.error(e)
            job_result.set_status(JobResultStatusChoices.STATUS_COMPLETED)
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        job_result.set_status(JobResultStatusChoices.STATUS_FAILED)
        BackupJob.enqueue_if_needed(backup, delay=delay, job_id=job_result.job_id)

    job_result.save()

    # Clear queue of old jobs
    BackupJob.objects.filter(
        backup=backup,
        status__in=JobResultStatusChoices.TERMINAL_STATE_CHOICES
    ).exclude(
        pk=job_result.pk
    ).delete()


logger = get_logger()
