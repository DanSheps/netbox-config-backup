import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from netbox_config_backup.models import BackupJob
from netbox_config_backup.tasks import backup_job
from netbox_config_backup.utils import remove_queued
from netbox_config_backup.utils.rq import can_backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', dest='time', help="time")
        parser.add_argument('--device', dest='device', help="Device Name")

    def run_backup(self, backup):
        if can_backup(backup):
            backupjob = backup.jobs.filter(backup__device=backup.device).last()
            if backupjob is None:
                backupjob = BackupJob.objects.create(
                    backup=backup,
                    scheduled=timezone.now(),
                    uuid=uuid.uuid4()
                )
            backup_job(backupjob.pk)
        remove_queued(backup)

    def handle(self, *args, **options):
        from netbox_config_backup.models import Backup
        if options['device']:
            print(f'Running:{options.get("device")}| ')
            backup = Backup.objects.filter(device__name=options['device']).first()
            if backup:
                self.run_backup(backup)
            else:
                raise Exception('Device not found')
        else:
            for backup in Backup.objects.all():
                self.run_backup(backup)

