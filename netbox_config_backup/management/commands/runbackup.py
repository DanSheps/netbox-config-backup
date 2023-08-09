import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_config_backup.tasks import backup_job
from netbox_config_backup.utils import remove_queued
from netbox_config_backup.utils.rq import can_backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', dest='time', help="time")
        parser.add_argument('--device', dest='device', help="Device Name")

    def run_backup(self, backup):
        if can_backup(backup):
            backupjob = backup.jobs.filter(backup__device__name=backup.device).last()
            backup_job(backupjob.pk)
        remove_queued(backup)

    def handle(self, *args, **options):
        from netbox_config_backup.models import Backup
        if options['device']:
            backup = Backup.objects.filter(device=options['device'])
            self.run_backup(backup)
        else:
            for backup in Backup.objects.all():
                self.run_backup(backup)

