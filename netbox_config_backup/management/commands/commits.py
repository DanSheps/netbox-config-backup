import datetime
from django.core.management.base import BaseCommand

from netbox_config_backup.git import repository
from netbox_config_backup.models import Backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--device', dest='device', help="Device Name")
        parser.add_argument('--uuid', dest='uuid', help="UUID")
        parser.add_argument('--action', dest='action', help="Action (rebuild, commit)", default='rebuild')

    def commit_unstaged(self, backup):
        commit = None
        status = repository.status()
        for file in status.unstaged:
            file = file.decode('ascii')
            uuid, type = file.split('.')
            if str(uuid) == str(backup.uuid):
                repository.add(file)

        if status.staged.get('add') or status.staged.get('modify') or status.staged.get('delete'):
            print(f'Committing changes for {backup}')
            commit = repository.commit(f'Rebuilding BCTC for {backup.device.name} with unstaged files')
        return commit

    def handle(self, *args, **options):
        print(f'Running Commit Maintenance')
        backup = None
        if options.get('uuid', None):
            backup = Backup.objects.get(uuid=options['uuid'])
        elif options.get('device', None):
            backup = Backup.objects.get(device__name=options['device'])

        if options.get('action', 'commit') not in ['commit', 'rebuild']:
            options['action'] = 'rebuild'

        if options.get('action', 'commit'):
            print('\tAction: Committing unstaged Changes')
        else:
            print('\tAction: Rebuild BCTC')

        backups = []
        if backup:
            backups = [backup]
        else:
            backups = Backup.objects.all()

        for backup in backups:
            print(f'Starting Commit Maintenance for {backup}')
            commit = self.commit_unstaged(backup)
            if options.get('action', 'commit'):
                if commit:
                    print(f'Updating BCTC for {backup} with commit: {commit}')
                    backup.update_commit_tree(commit=commit, depth=1)
            elif options.get('action', 'rebuild'):
                print(f'Rebuilding BCTC for {backup}')
                backup.rebuild_bctc()
