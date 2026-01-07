from django.core.management.base import BaseCommand
from django.utils import timezone

from core.choices import JobStatusChoices
from netbox_config_backup.jobs.backup import BackupRunner
from netbox_config_backup.models import Backup, BackupJob


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
                if options.get('time') == 'now':
                    for job in backup.jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES):
                        print(f'Clearing old jobs: {job}')
                        job.status = JobStatusChoices.STATUS_ERRORED
                        job.data = (
                            {'error': 'Clearing stuck job'}
                            if not job.data
                            else job.data.update({'error': 'Clearing stuck job'})
                        )
                        job.clean()
                        job.save()

                self.run_backup(backup)
            else:
                raise Exception('Device not found')
        else:
            if options['time'] == 'now':
                print('Setting all scheduled jobs to start immediately')
                jobs = BackupJob.objects.filter(status=JobStatusChoices.STATUS_SCHEDULED)
                for job in jobs:
                    job.scheduled = timezone.now()
                BackupJob.objects.bulk_update(jobs, ['scheduled'])

            self.run_backup()
