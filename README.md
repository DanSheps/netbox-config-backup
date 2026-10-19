# Netbox Configuration Backup

[![PyPI](https://img.shields.io/pypi/v/netbox-config-backup.svg)](https://pypi.org/project/netbox-config-backup/)
[![Python](https://img.shields.io/pypi/pyversions/netbox-config-backup.svg)](https://pypi.org/project/netbox-config-backup/)
[![NetBox](https://img.shields.io/badge/NetBox-4.7%2B-success.svg)](https://github.com/netbox-community/netbox)
[![CI](https://github.com/dansheps/netbox-config-backup/actions/workflows/ci.yml/badge.svg)](https://github.com/dansheps/netbox-config-backup/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

A configuration backup system using netbox and napalm to backup devices into a git repository

# Features

* Connects to any device that supports napalm and provides both a running configuration and startup configuration
* Stores backups in a git repository
* Runs as a scheduled task through Django RQ
* Only displays backups with changes
* Provides both configuration download and diffs for point-in-time backups

# Future

* Allow github repositories
* Add job "discovery" based on specific criteria (napalm enabled, device role switch, has primary ip as an example)
* Add RQ job to ensure all backups are queued
* Allow manual queueing of job
* Add API endpoint to trigger backup
* Add signal(s) to trigger backup

# Installation

1. Install from PyPI (`pip install netbox-config-backup`)
   1. This should install `netbox_napalm_plugin` which is also required
2. Edit netbox configuration:
```pyython
PLUGINS = [
    'netbox_config_backup',
    # Other plugins here
]

PLUGINS_CONFIG = {
    'netbox_config_backup': {
        # Parent folder must exist and be writable by your RQ worker and readable by the WSGI process
        'repository': '/path/to/git/repository',
        'committer': 'User <email>',
        'author': 'User <email>',
        # Freqency of backups in seconds, can be anywhere 0+ (Recommended is 1800 (30 minutes) or 3600 (1 hr)
        'frequency': 3600
    }
}
```
3. Migrate: `python3 netbox/manage.py migrate`
4. Create appropriate Napalm configurations for all devices you will be backing up
5. Create your first device backup

### Cleanup Old Version

If you are coming from an older version, please remove the custom RQ worker as it is no longer required

## Logging

To enable logging, add the following to your configuration.py under LOGGING:

```python
        'netbox_config_backup': {
            'handlers': ['enter_your_handlers_here'],
            'level': 'desired_log_level',
            'propagate': True,
        },
```
