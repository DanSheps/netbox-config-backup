from importlib.metadata import metadata

from netbox.plugins import PluginConfig

metadata = metadata('netbox_config_backup')


class NetboxConfigBackup(PluginConfig):
    name = metadata.get('Name').replace('-', '_')
    verbose_name = metadata.get('Name').replace('-', ' ').title()
    description = metadata.get('Summary')
    version = metadata.get('Version')
    author = metadata.get('Author')
    author_email = metadata.get('Author-email')
    base_url = 'configbackup'
    min_version = '4.1.0'
    max_version = '4.1.99'
    required_settings = [
        'repository',
        'committer',
        'author',
    ]
    default_settings = {
        # Frequency in seconds
        'frequency': 3600,
    }
    queues = [
        'jobs'
    ]
    graphql_schema = 'graphql.schema.schema'

    def ready(self):
        super().ready()
        from netbox import settings
        from netbox_config_backup.jobs.backup import BackupRunner
        from netbox_config_backup.models import BackupJob, Backup

        frequency = settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency') / 60
        BackupRunner.enqueue_once(interval=frequency)


config = NetboxConfigBackup
