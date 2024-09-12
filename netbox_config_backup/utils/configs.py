from datetime import datetime
import re

from netbox_config_backup.utils.logger import get_logger
logger = get_logger()


def check_config_save_status(d):
    logger.info(f'Switch: {d.hostname}')
    platform = {
        'ios': {
            'running': {
                'command': 'show running-config | inc ! Last configuration change',
                'regex': r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) \S+ \S+ (?P<month>\S+) (?P<day>\d+) (?P<year>\S+)(?: by \S+)?'
            },
            'startup':{
                'command': 'show startup-config | inc ! Last configuration change',
                'regex': r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) \S+ \S+ (?P<month>\S+) (?P<day>\d+) (?P<year>\S+)(?: by \S+)?'
            }
        },
        'nxos_ssh': {
            'running': {
                'command': 'show running-config | inc "!Running configuration last done at:"',
                'regex': r'(?P<month>\S+)\s+(?P<day>\d+) (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) (?P<year>\d+)'
            },
            'startup': {
                'command': 'show startup-config | inc "!Startup config saved at:"',
                'regex': r'(?P<month>\S+)\s+(?P<day>\d+) (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) (?P<year>\d+)'
            }
        },
    }

    try:
        datetimes = {
            'running': None,
            'startup': None
        }
        dates = {
            'running': None,
            'startup': None
        }
        for file in ['running', 'startup']:
            command = d.cli(commands=[platform.get(d.platform, {}).get(file, {}).get('command', '')])
            result = list(command.values()).pop()
            regex = platform.get(d.platform, {}).get(file, {}).get('regex', '')
            search = re.search(regex, result)

            if search is not None and search.groupdict():
                status = search.groupdict()
                year = status.get('year')
                month = status.get('month')
                day = f"0{int(status.get('day'))}" if int(status.get('day')) < 10 else f"{int(status.get('day'))}"
                hours = status.get('hours')
                minutes = status.get('minutes')
                seconds = status.get('seconds')

                date = f'{year}-{month}-{day} {hours}:{minutes}:{seconds}'

                dates[file] = date
                datetimes[file] = datetime.strptime(date, '%Y-%b-%d %H:%M:%S')
            else:
                logger.debug(f'\tNo {file} time found, platform: {d.platform}')

        if datetimes['running'] is None and datetimes['startup'] is not None:
            logger.debug(f'\tValid backup as booted from startup')
            return True
        elif datetimes['startup'] is None:
            logger.debug(f'\tNo startup time')
            return
        elif datetimes['running'] <= datetimes['startup']:
            logger.debug(f'\tRunning config less then startup')
            return True
        elif datetimes['running'] > datetimes['startup']:
            logger.debug(f'\tRunning config greater then startup')
            return False

    except Exception as e:

        logger.error(f'Exception when trying to check config status: {e}')