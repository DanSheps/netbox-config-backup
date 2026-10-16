from datetime import datetime
import re

from django.utils import timezone

from netbox_config_backup.choices import FileTypeChoices
from netbox_config_backup.utils.logger import get_logger

logger = get_logger()


def check_config_save_status(d):
    logger.debug(f'Switch: {d.hostname}')
    platform = {
        'ios': {
            FileTypeChoices.TYPE_RUNNING: {
                'command': 'show running-config | inc ! Last configuration change',
                'regex': r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) \S+ \S+ (?P<month>\S+) (?P<day>\d+) (?P<year>\S+)(?: by \S+)?',  # noqa: E501
            },
            FileTypeChoices.TYPE_STARTUP: {
                'command': 'show startup-config | inc ! Last configuration change',
                'regex': r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) \S+ \S+ (?P<month>\S+) (?P<day>\d+) (?P<year>\S+)(?: by \S+)?',  # noqa: E501
            },
        },
        'nxos_ssh': {
            FileTypeChoices.TYPE_RUNNING: {
                'command': 'show running-config | inc "!Running configuration last done at:"',
                'regex': r'(?P<month>\S+)\s+(?P<day>\d+) (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) (?P<year>\d+)',  # noqa: E501
            },
            FileTypeChoices.TYPE_STARTUP: {
                'command': 'show startup-config | inc "!Startup config saved at:"',
                'regex': r'(?P<month>\S+)\s+(?P<day>\d+) (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+) (?P<year>\d+)',  # noqa: E501
            },
        },
    }

    try:
        datetimes = {FileTypeChoices.TYPE_RUNNING: None, FileTypeChoices.TYPE_STARTUP: None, 'status': None}
        dates = {FileTypeChoices.TYPE_RUNNING: None, FileTypeChoices.TYPE_STARTUP: None, 'status': None}
        for file in [FileTypeChoices.TYPE_RUNNING, FileTypeChoices.TYPE_STARTUP]:
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
                datetimes[file] = timezone.make_aware(datetime.strptime(date, '%Y-%b-%d %H:%M:%S'))
            else:
                logger.debug(f'\tNo {file} time found, platform: {d.platform}')

        if datetimes[FileTypeChoices.TYPE_RUNNING] is None and datetimes[FileTypeChoices.TYPE_STARTUP] is not None:
            logger.debug('\tValid backup as booted from startup')
            datetimes.update({'status': True})
            dates.update({'status': True})
            return datetimes
        elif datetimes[FileTypeChoices.TYPE_STARTUP] is None:
            logger.debug('\tNo startup time')
            return datetimes
        elif datetimes[FileTypeChoices.TYPE_RUNNING] <= datetimes[FileTypeChoices.TYPE_STARTUP]:
            logger.debug('\tRunning config less then startup')
            datetimes.update({'status': True})
            dates.update({'status': True})
            return datetimes
        elif datetimes[FileTypeChoices.TYPE_RUNNING] > datetimes[FileTypeChoices.TYPE_STARTUP]:
            logger.debug('\tRunning config greater then startup')
            datetimes.update({'status': False})
            dates.update({'status': False})
            return datetimes

    except Exception as e:
        logger.warning(f'Exception when trying to check config status: {e}')
