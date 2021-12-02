
from netbox_config_backup.models import BackupCommitTreeChange
from netbox_config_backup.tables import BackupsTable

def get_backup_tables(instance):
    def get_backup_table(data, file):
        backups = []
        for row in data:
            commit = row.commit
            previous = None
            if row.old is not None:
                try:
                    previous = BackupCommitTreeChange.objects.filter(new=row.old).first().commit.sha
                except AttributeError:
                    pass
            backup = {'pk': instance.pk, 'date': commit.time, 'index': commit.sha, 'previous': previous, 'file': file}
            backups.append(backup)

        table = BackupsTable(backups)
        return table

    tree = BackupCommitTreeChange.objects.filter(commit__backup__pk=instance.pk).prefetch_related('old', 'new',
                                                                                                  'commit')
    changes = {
        'running': tree.filter(new__file__endswith='running'),
        'startup': tree.filter(new__file__endswith='startup')
    }

    tables = {}
    for file in ['running', 'startup']:
        try:
            tables.update({file: get_backup_table(changes.get(file, []), file)})
        except KeyError:
            tables.update({file: get_backup_table([], file)})

    return tables
