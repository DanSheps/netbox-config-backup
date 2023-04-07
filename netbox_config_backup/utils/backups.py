import logging

logger = logging.getLogger(f"netbox_config_backup")


def get_backup_tables(instance):
    from netbox_config_backup.models import BackupCommitTreeChange
    from netbox_config_backup.tables import BackupsTable

    def get_backup_table(data):
        backups = []
        for row in data:
            commit = row.commit
            current = row
            previous = row.backup.changes.filter(file__type=row.file.type, commit__time__lt=commit.time).last()
            backup = {'pk': instance.pk, 'date': commit.time, 'current': current, 'previous': previous}
            backups.append(backup)

        table = BackupsTable(backups)
        return table

    backups = BackupCommitTreeChange.objects.filter(backup=instance).prefetch_related('backup', 'new', 'old', 'commit',
                                                                                      'file').order_by('commit__time')

    tables = {}
    for file in ['running', 'startup']:
        try:
            tables.update({file: get_backup_table(backups.filter(file__type=file))})
        except KeyError:
            tables.update({file: get_backup_table([])})

    return tables
