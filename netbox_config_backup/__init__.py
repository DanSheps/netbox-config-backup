from datetime import datetime
from importlib.metadata import metadata

from django.utils import timezone
from django_rq import get_queue

from core.choices import JobStatusChoices
from netbox.plugins import PluginConfig
from netbox_config_backup.utils.logger import get_logger

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

    def ready(self, *args, **kwargs):
        super().ready()
        import sys
        if len(sys.argv) > 1 and 'rqworker' in sys.argv[1]:
            from netbox_config_backup.jobs.backup import BackupRunner


config = NetboxConfigBackup
