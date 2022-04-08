import datetime
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        from netbox_config_backup.git import repository
        from netbox_config_backup.models import Backup, BackupCommit, BackupFile, BackupObject, BackupCommitTreeChange
        LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

        print(f'Fetching Git log')
        log = reversed(repository.log())
        print(f'Fetched Git log')

        for entry in log:
            time = entry.get('time', datetime.datetime.now()).replace(tzinfo=LOCAL_TIMEZONE)

            try:
                bc = BackupCommit.objects.get(sha=entry.get('sha', None))
            except BackupCommit.DoesNotExist:
                bc = BackupCommit(sha=entry.get('sha', None), time=time)
            print(f'Saving commit: {bc.sha} at time {bc.time} with parent {entry.get("parents", [])}')
            bc.save()
            for change in entry.get('changes'):
                backup = None
                backupfile = None

                change_data = {}
                for key in ['old', 'new']:
                    sha = change.get(key, {}).get('sha', None)
                    file = change.get(key, {}).get('path', None)
                    if file is not None and file is not None:
                        uuid, type = file.split('.')
                        try:
                            backup = Backup.objects.get(uuid=uuid)
                        except Backup.DoesNotExist:
                            backup = Backup.objects.create(uuid=uuid, name=uuid)
                        try:
                            backupfile = BackupFile.objects.get(backup=backup, type=type)
                        except BackupFile.DoesNotExist:
                            backupfile = BackupFile.objects.create(backup=backup, type=type)
                        try:
                            object = BackupObject.objects.get(sha=sha)
                        except BackupObject.DoesNotExist:
                            object = BackupObject.objects.create(sha=sha)
                        change_data[key] = object

                    index = f'{key}-{sha}-{file}'
                    print(f'\t\t{index}')

                try:
                    bctc = BackupCommitTreeChange.objects.get(
                        backup=backup,
                        file=backupfile,
                        commit=bc,
                        type=change.get('type', None),
                        old=change_data.get('old', None),
                        new=change_data.get('new', None)
                    )
                except BackupCommitTreeChange.DoesNotExist:
                    bctc = BackupCommitTreeChange.objects.create(
                        backup=backup,
                        file=backupfile,
                        commit=bc,
                        type=change.get('type', None),
                        old=change_data.get('old', None),
                        new=change_data.get('new', None)
                    )

                newsha = bctc.new.sha if bctc.new else None
                oldsha = bctc.old.sha if bctc.old else None
                print(f'\tSaving change {bc.sha}, {oldsha}, {newsha}')
            print("")
