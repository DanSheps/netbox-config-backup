from django.core.management.base import BaseCommand
from django.utils import timezone

from netbox_config_backup.jobs.backup import BackupRunner
from netbox_config_backup.models import Backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', dest='time', help="time")
        parser.add_argument('--device', dest='device', help="Device Name", required=True)

    def handle(self, *args, **options):
        print(f'Running backup for: {options.get("device")}')
        backup = Backup.objects.filter(device__name=options['device']).first()
        if not backup:
            backup = Backup.objects.filter(name=options['device']).first()

        if backup:
            job = backup.jobs.last()
            job.scheduled = timezone.now()
            job.clean()
            job.save()
            BackupRunner.enqueue(backup=backup, immediate=True)
            # run_backup(job.pk)
        else:
            raise Exception('Device not found')
