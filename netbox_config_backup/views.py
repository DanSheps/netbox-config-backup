import logging

from django.shortcuts import get_object_or_404, render
from django.views import View

from extras.choices import JobResultStatusChoices
from netbox.views.generic import ObjectDeleteView, ObjectEditView, ObjectView, ObjectListView

from netbox_config_backup.forms import BackupForm
from netbox_config_backup.git import GitBackup
from netbox_config_backup.models import Backup, BackupJob, BackupCommitTreeChange, BackupCommit, BackupObject
from netbox_config_backup.tables import BackupTable
from netbox_config_backup.utils import get_backup_tables, Differ

logger = logging.getLogger(f"netbox_config_backup")


class BackupListView(ObjectListView):
    queryset = Backup.objects.all()
    table = BackupTable
    action_buttons = ('add',)


class BackupView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/device.html'

    def get_extra_context(self, request, instance):

        tables = get_backup_tables(instance)

        jobs = BackupJob.objects.filter(backup=instance).order_by()
        is_running = True if jobs.filter(status=JobResultStatusChoices.STATUS_RUNNING).count() > 0 else False
        is_pending = True if jobs.filter(status=JobResultStatusChoices.STATUS_PENDING).count() > 0 else False

        job_status = None
        if is_pending:
            job_status = 'Pending'
        if is_running:
            job_status = 'Running'

        if BackupJob.is_queued(instance) is False:
            logger.debug(f'{instance}: Queuing Job')
            BackupJob.enqueue_if_needed(instance)

        status = {
            'status': job_status,
            'scheduled': BackupJob.is_queued(instance),
            'next_attempt': instance.next_attempt,
            'last_job': instance.jobs.filter(completed__isnull=False).last(),
            'last_success': instance.last_backup,
            'last_change': instance.last_change,
        }

        return {
            'running': tables.get('running', {}),
            'startup': tables.get('startup', {}),
            'status': status,
        }


class BackupEditView(ObjectEditView):
    queryset = Backup.objects.all()
    form = BackupForm


class BackupDeleteView(ObjectDeleteView):
    queryset = Backup.objects.all()


class ConfigView(View):
    template_name = 'netbox_config_backup/config.html'

    def get(self, request, pk, current):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        current = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=current)

        path = f'{current.file.path}'

        repo = GitBackup()
        config = repo.read(path, current.commit.sha)

        previous = None
        if current is not None and current.old is not None:
            try:
                previous = backup.changes.filter(file__type=current.file.type, commit__time__lt=current.commit.time).last()
            except:
                pass

        return render(request, 'netbox_config_backup/config.html', {
            'object': backup,
            'backup_config': config,
            'current': current,
            'previous': previous,
            'active_tab': 'config',
        })


class DiffView(View):
    template_name = 'netbox_config_backup/diff.html'

    def get(self, request, pk, current, previous=None):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        current = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=current)
        previous = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=previous)

        path = f'{current.file.path}'

        repo = GitBackup()

        previous_sha = previous.commit.sha if previous.commit is not None else 'HEAD'
        current_sha = current.commit.sha if current.commit is not None else None

        if backup.device and backup.device.platform.napalm_driver in ['ios', 'nxos']:
            new = repo.read(path, current_sha)
            old = repo.read(path, previous_sha)
            differ = Differ(old, new)
            diff = differ.cisco_compare()
        else:
            new = repo.read(path, current_sha)
            old = repo.read(path, previous_sha)
            differ = Differ(old, new)
            diff = differ.compare()

        for idx, line in enumerate(diff):
            diff[idx] = line.rstrip()

        return render(request, 'netbox_config_backup/diff.html', {
            'object': backup,
            'diff': diff,
            'current': current,
            'previous': previous,
            'active_tab': 'diff',
        })
