###################################################################
#  This file serves as a base configuration for testing purposes  #
#  only. It is not intended for production use.                   #
###################################################################

ALLOWED_HOSTS = ['*']

DATABASE = {
    'NAME': 'netbox',
    'USER': 'netbox',
    'PASSWORD': 'netbox',
    'HOST': 'localhost',
    'PORT': '',
    'CONN_MAX_AGE': 300,
}

PLUGINS = [
    'netbox_napalm_plugin',
    'netbox_config_backup',
]

PLUGINS_CONFIG = {
    'netbox_config_backup': {
        'repository': '/tmp/repository/',
        'committer': 'Test Committer <test@testgit.com>',
        'author': 'Test Committer <test@testgit.com>',
        'frequency': 3600,
    },
    'netbox_napalm_plugin': {
        'NAPALM_USERNAME': 'xxx',
        'NAPALM_PASSWORD': 'yyy',
    }
}

REDIS = {
    'tasks': {
        'HOST': 'localhost',
        'PORT': 6379,
        'PASSWORD': '',
        'DATABASE': 0,
        'SSL': False,
    },
    'caching': {
        'HOST': 'localhost',
        'PORT': 6379,
        'PASSWORD': '',
        'DATABASE': 1,
        'SSL': False,
    }
}

SECRET_KEY = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
