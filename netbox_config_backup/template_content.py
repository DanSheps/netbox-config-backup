import logging

from extras.plugins import PluginTemplateExtension

from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.utils import get_backup_tables

logger = logging.getLogger(f"netbox_config_backup")


class DeviceBackups(PluginTemplateExtension):
    model = 'dcim.device'

    def full_width_page(self):
        device = self.context.get('object', None)
        devices = Backup.objects.filter(device=device) if device is not None else Backup.objects.none()
        if devices.count() > 0:
            instance = devices.first()
            tables = get_backup_tables(instance)

            if BackupJob.is_queued(instance) is False:
                logger.debug('Queuing Job')
                BackupJob.enqueue(instance)

            return self.render('netbox_config_backup/inc/backup_tables.html', extra_context={
                'running': tables.get('running'),
                'startup': tables.get('startup'),
            })

        return ''


template_extensions = [DeviceBackups]
