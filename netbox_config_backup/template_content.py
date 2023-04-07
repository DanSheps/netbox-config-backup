import logging

from extras.plugins import PluginTemplateExtension

from netbox_config_backup.models import Backup, BackupJob, BackupCommitTreeChange
from netbox_config_backup.tables import BackupsTable
from netbox_config_backup.utils.backups import get_backup_tables
from utilities.htmx import is_htmx

logger = logging.getLogger(f"netbox_config_backup")


class DeviceBackups(PluginTemplateExtension):
    model = 'dcim.device'

    def full_width_page(self):
        request = self.context.get('request')
        def build_table(instance):
            bctc = BackupCommitTreeChange.objects.filter(
                backup=instance,
                file__isnull=False
            )
            table = BackupsTable(bctc, user=request.user)
            table.configure(request)

            return table

        device = self.context.get('object', None)
        devices = Backup.objects.filter(device=device) if device is not None else Backup.objects.none()
        if devices.count() > 0:
            instance = devices.first()
            table = build_table(instance)

            if BackupJob.is_queued(instance) is False:
                logger.debug(f'{instance}: Queuing Job')
                BackupJob.enqueue(instance)

            if is_htmx(request):
                return self.render('htmx/table.html', extra_context={
                    'object': instance,
                    'table': table,
                    'preferences': {},
                })
            return self.render('netbox_config_backup/inc/backup_tables.html', extra_context={
                'object': instance,
                'table': table,
                'preferences': request.user.config,
            })

        return ''


template_extensions = [DeviceBackups]
