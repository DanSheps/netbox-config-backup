import logging

import uuid
from django.utils import timezone
from django_rq import get_queue
from rq.registry import ScheduledJobRegistry

from dcim.choices import DeviceStatusChoices
from core.choices import JobStatusChoices
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models.jobs import BackupJob

logger = logging.getLogger(f"netbox_config_backup")


def can_backup(backup):
    logger.debug(f'Checking backup suitability for {backup}')
    if backup.device is None:
        logger.info(f'No device for {backup}')
        return False
    elif backup.status == StatusChoices.STATUS_DISABLED:
        logger.info(f'Backup disabled for {backup}')
        return False
    elif backup.device.status in [DeviceStatusChoices.STATUS_OFFLINE,
                                DeviceStatusChoices.STATUS_FAILED,
                                DeviceStatusChoices.STATUS_INVENTORY,
                                DeviceStatusChoices.STATUS_PLANNED]:
        logger.info(f'Backup disabled for {backup} due to device status ({backup.device.status})')
        return False
    elif (backup.ip is None and backup.device.primary_ip is None) or backup.device.platform is None or \
            hasattr(backup.device.platform, 'napalm') is False or backup.device.platform.napalm is None or \
            backup.device.platform.napalm.napalm_driver == '' or backup.device.platform.napalm.napalm_driver is None:
        if backup.ip is None and backup.device.primary_ip is None:
            logger.warning(f'Backup disabled for {backup} due to no primary IP ({backup.device.status})')
        elif backup.device.platform is None:
            logger.warning(f'Backup disabled for {backup} due to platform not set ({backup.device.status})')
        elif hasattr(backup.device.platform, 'napalm') is False or backup.device.platform.napalm is None:
            logger.warning(
                f'Backup disabled for {backup} due to platform having no napalm config ({backup.device.status})'
            )
        elif backup.device.platform.napalm.napalm_driver == '' or backup.device.platform.napalm.napalm_driver is None:
            logger.warning(f'Backup disabled for {backup} due to napalm driver not set ({backup.device.status})')
        return False

    return True
