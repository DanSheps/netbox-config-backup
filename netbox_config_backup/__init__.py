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
        # Frequency in seconds (Deprecated)
        'frequency': 3600,
        # Frequency of backups in minutes
        'backup_frequency': 60,
        # Frequency of the job runner in minutes
        'job_frequency': 5,
        # Offset for Jobs in minutes (to offset jobs after a restart)
        'offset': 6,
        # Number of jobs per run
        'workers': 10,
    }
    queues = ['jobs']
    graphql_schema = 'graphql.schema.schema'

    def ready(self, *args, **kwargs):
        super().ready()
        import sys

        if len(sys.argv) > 1 and 'rqworker' in sys.argv[1]:
            from netbox_config_backup.jobs import BackupRunner, BackupHousekeeping  # noqa: F401


config = NetboxConfigBackup
