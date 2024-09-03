from importlib.metadata import metadata

from netbox.plugins import PluginConfig

metadata = metadata('netbox_config_backup')


class NetboxConfigBackup(PluginConfig):
    name = metadata.get('Name').replace('-', '_')
    verbose_name = metadata.get('Summary')
    description = metadata.get('Description')
    version = metadata.get('Version')
    author = metadata.get('Author')
    author_email = metadata.get('Author-email')
    base_url = 'configbackup'
    min_version = '3.5.8'
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


config = NetboxConfigBackup
