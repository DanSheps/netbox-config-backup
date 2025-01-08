from django.core.management.base import BaseCommand

from netbox_config_backup.jobs.backup import BackupRunner
from netbox_config_backup.models import Backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', dest='time', help="time")
        parser.add_argument('--device', dest='device', help="Device Name")

    def run_backup(self, backup=None):
        BackupRunner.enqueue(backup=backup, immediate=True)

    def handle(self, *args, **options):
        if options['device']:
            print(f'Running backup for: {options.get("device")}')
            backup = Backup.objects.filter(device__name=options['device']).first()
            if not backup:
                backup = Backup.objects.filter(name=options['device']).first()
            if backup:
                self.run_backup(backup)
            else:
                raise Exception('Device not found')
        else:
            self.run_backup()

