import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from netbox_config_backup.models import BackupJob
from netbox_config_backup.tasks import backup_job
from netbox_config_backup.utils import remove_queued
from netbox_config_backup.utils.rq import can_backup


class Command(BaseCommand):

    def handle(self, *args, **options):
        from netbox_config_backup.models import Backup
        print(f'Backup Name\t\tDevice Name\t\tIP')
        for backup in Backup.objects.filter(device__isnull=False):
            if backup.ip:
                ip = backup.ip
            else:
                ip = backup.device.primary_ip

            name = f'{backup.name}'
            if len(backup.name) > 15:
                name = f'{name}\t'
            elif len(backup.name) > 7:
                name = f'{name}\t\t'
            else:
                name = f'{name}\t\t\t'

            device_name = f'{backup.device.name}'
            if len(backup.device.name) > 15:
                device_name = f'{device_name}\t'
            elif len(backup.device.name) > 7:
                device_name = f'{device_name}\t\t'
            else:
                device_name = f'{device_name}\t\t\t'

            print(f'{name}{device_name}{ip}')
