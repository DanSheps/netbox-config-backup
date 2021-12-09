import logging
import re

from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.views import View

from extras.choices import JobResultStatusChoices

from netbox_plugin_extensions.views.generic import PluginObjectListView, PluginObjectView, PluginObjectEditView, \
    PluginObjectDeleteView

from netbox_config_backup.forms import BackupForm
from netbox_config_backup.git import GitBackup
from netbox_config_backup.models import Backup, BackupJob, BackupCommitTreeChange
from netbox_config_backup.tables import BackupTable
from netbox_config_backup.utils import get_backup_tables, Differ

logger = logging.getLogger(f"netbox_config_backup")


class BackupListView(PluginObjectListView):
    queryset = Backup.objects.all()
    table = BackupTable
    action_buttons = ('add',)


class BackupView(PluginObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/device.html'

    def get_extra_context(self, request, instance):

        tables = get_backup_tables(instance)

        jobs = BackupJob.objects.filter(backup=instance).order_by()
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
            'startup': tables.get('startup', {}),
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

        try:
            bctc = BackupCommitTreeChange.objects.get(commit__sha=index, new__file=path)
        except BackupCommitTreeChange.DoesNotExist:
            bctc = None

        repo = GitBackup()
        config = repo.read(path, index)

        previous = None
        if bctc is not None and bctc.old is not None:
            try:
                prevbctc = BackupCommitTreeChange.objects.get(new__sha=bctc.old.sha, new__file=path)
                previous = prevbctc.commit.sha
            except:
                pass

        return render(request, 'netbox_config_backup/config.html', {
            'object': backup,
            'backup_config': config,
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

        if backup.device and backup.device.platform.napalm_driver in ['ios', 'nxos']:
            differ = Differ()
            old = repo.read(path, previous)
            new = repo.read(path, index)
            diff = differ.cisco_compare(old.splitlines(), new.splitlines())
        else:
            diff = list(repo.diff(path, previous, index))
        for idx, line in enumerate(diff):
            diff[idx] = line.rstrip()


        return render(request, 'netbox_config_backup/diff.html', {
            'object': backup,
            'diff': diff,
            'index': index,
            'previous': previous,
            'file': file,
            'active_tab': 'diff',
        })
