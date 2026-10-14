from django.core.management.base import BaseCommand
from netbox_config_backup.jobs import BackupHousekeeping


class Command(BaseCommand):

    def handle(self, *args, **options):
        BackupHousekeeping.enqueue(immediate=True)