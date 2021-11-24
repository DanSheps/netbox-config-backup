import os

from netbox import settings


def get_repository_dir():
    repository = settings.PLUGINS_CONFIG.get("netbox_config_backup", {}).get("repository")
    if repository == os.path.abspath(repository) or repository == (os.path.abspath(repository) + os.path.sep):
        return repository

    return f'{os.path.dirname(os.path.dirname(settings.BASE_DIR))}{os.path.sep}{repository}'