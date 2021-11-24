import logging

from extras.choices import JobResultStatusChoices
from extras.plugins import PluginTemplateExtension
from netbox_config_backup.git import GitBackup

from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.tables import BackupsTable

logger = logging.getLogger(f"netbox_config_backup")

class DeviceBackups(PluginTemplateExtension):
    model = 'dcim.device'

    def full_width_page(self):
        device = self.context.get('object', None)
        devices = Backup.objects.filter(device=device) if device is not None else Backup.objects.none()
        if devices.count() > 0:
            instance = devices.first()

            def get_backup_table(data, file):
                backups = []
                for row in data:
                    previous = row.get('change', {}).get('previous', None)
                    date = row.get('time')
                    backup = {'pk': instance.pk, 'date': date, 'index': row.get('sha'), 'previous': previous,
                              'file': file}
                    backups.append(backup)

                table = BackupsTable(backups)
                return table

            repo = GitBackup()
            jobs = BackupJob.objects.filter(backup=instance)
            tables = {}
            for file in ['running', 'startup']:
                path = f'{instance.uuid}.{file}'
                try:
                    log = repo.log(path)
                    tables.update({file: get_backup_table(log, file)})
                except KeyError:
                    tables.update({file: get_backup_table([], file)})

            is_running = True if jobs.filter(status=JobResultStatusChoices.STATUS_RUNNING).count() > 0 else False
            is_pending = True if jobs.filter(status=JobResultStatusChoices.STATUS_PENDING).count() > 0 else False

            status = None
            if is_pending:
                status = 'Pending'
            if is_running:
                status = 'Running'

            if BackupJob.is_queued(instance) is False:
                logger.debug('Queuing Job')
                BackupJob.enqueue(instance)

            return self.render('netbox_config_backup/inc/backup_tables.html', extra_context={
                'running': tables.get('running'),
                'startup': tables.get('startup'),
            })

        return ''


template_extensions = [DeviceBackups]
