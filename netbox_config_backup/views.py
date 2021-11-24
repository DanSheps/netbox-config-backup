import logging
from datetime import datetime

from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.views import View

from extras.choices import JobResultStatusChoices

from netbox_plugin_extensions.views.generic import PluginObjectListView, PluginObjectView, PluginObjectEditView, \
    PluginObjectDeleteView

from netbox_config_backup.forms import BackupForm
from netbox_config_backup.git import GitBackup
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.tables import BackupTable, BackupsTable

logger = logging.getLogger(f"netbox_config_backup")


class BackupListView(PluginObjectListView):
    queryset = Backup.objects.all()
    table = BackupTable
    action_buttons = ('add',)


class BackupView(PluginObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/device.html'

    def get_extra_context(self, request, instance):
        def get_backup_table(data, file):
            backups = []
            for row in data:
                previous = row.get('change', {}).get('previous', None)
                date = row.get('time')
                backup = {'pk': instance.pk, 'date': date, 'index': row.get('sha'), 'previous': previous, 'file': file}
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

        return {
            'running': tables.get('running', {}),
            'startup': tables.get('running', {}),
            'status': status,
            'active_tab': 'backup',
        }


class BackupEditView(PluginObjectEditView):
    queryset = Backup.objects.all()
    model_form = BackupForm


class BackupDeleteView(PluginObjectDeleteView):
    queryset = Backup.objects.all()


class ConfigView(View):
    template_name = 'netbox_config_backup/config.html'

    def get(self, request, pk, file, index):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        if file not in ['running', 'startup']:
            return HttpResponseNotFound('<h1>No valid file defined</h1>')

        path = f'{backup.uuid}.{file}'

        repo = GitBackup()
        log = repo.log(path)
        config = repo.read(path, index)

        previous = None
        log_index = [ind for ind in log if ind.get('sha') == index]
        if len(log_index) > 0:
            commit = log_index.pop(0)
            previous = commit.get('change', {}).get('previous', None)

        return render(request, 'netbox_config_backup/config.html', {
            'object': backup,
            'config': config,
            'index': index,
            'previous': previous,
            'file': file,
            'active_tab': 'config',
        })


class DiffView(View):
    template_name = 'netbox_config_backup/diff.html'

    def get(self, request, pk, file, index, previous=None):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        if file not in ['running', 'startup']:
            return HttpResponseNotFound('<h1>No valid file defined</h1>')

        path = f'{backup.uuid}.{file}'
        repo = GitBackup()
        previous = previous if previous is not None else 'HEAD'

        diff = repo.diff(path, previous, index)

        return render(request, 'netbox_config_backup/diff.html', {
            'object': backup,
            'diff': "\r\n".join(diff),
            'index': index,
            'previous': previous,
            'file': file,
            'active_tab': 'diff',
        })
