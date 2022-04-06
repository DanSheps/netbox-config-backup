import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_config_backup.tasks import backup_job


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', help="time")
        parser.add_argument('device', help="Device Name")

    def handle(self, *args, **options):
        from netbox_config_backup.models import Backup, BackupJob

        backupjob = BackupJob.objects.filter(backup__device__name=options['device']).last()
        backup_job(backupjob.pk)
