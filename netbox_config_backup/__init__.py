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
    min_version = '4.5.0'
    required_settings = [
        'repository',
        'committer',
        'author',
    ]
    default_settings = {
        # Frequency in seconds
        'frequency': 3600,
    }
    queues = ['jobs']
    graphql_schema = 'graphql.schema.schema'

    def ready(self, *args, **kwargs):
        super().ready()
        import sys

        if len(sys.argv) > 1 and 'rqworker' in sys.argv[1]:
            from netbox_config_backup.jobs import BackupRunner, BackupHousekeeping  # noqa: F401


config = NetboxConfigBackup
