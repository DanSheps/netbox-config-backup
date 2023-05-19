import logging

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, NoReverseMatch
from django.views import View

from extras.choices import JobResultStatusChoices
from netbox.views.generic import ObjectDeleteView, ObjectEditView, ObjectView, ObjectListView, ObjectChildrenView
from netbox_config_backup.filtersets import BackupFilterSet, BackupsFilterSet

from netbox_config_backup.forms import BackupForm, BackupFilterSetForm
from netbox_config_backup.git import GitBackup
from netbox_config_backup.models import Backup, BackupJob, BackupCommitTreeChange, BackupCommit, BackupObject
from netbox_config_backup.tables import BackupTable, BackupsTable
from netbox_config_backup.utils import get_backup_tables, Differ
from utilities.views import register_model_view, ViewTab

logger = logging.getLogger(f"netbox_config_backup")


class BackupListView(ObjectListView):
    queryset = Backup.objects.all()
    filterset = BackupFilterSet
    filterset_form = BackupFilterSetForm
    table = BackupTable
    action_buttons = ('add',)


@register_model_view(Backup)
class BackupView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/backup.html'

    def get_extra_context(self, request, instance):

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
            'status': status,
        }


@register_model_view(Backup, name='backups')
class BackupBackupsView(ObjectChildrenView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/backups.html'
    child_model = BackupCommitTreeChange
    table = BackupsTable
    filterset = BackupsFilterSet
    actions = ['config', 'diff']
    action_perms = {
        'config': {'view'},
        'diff': {'view'},
    }
    tab = ViewTab(
        label='View Backups',
        badge=lambda obj: BackupCommitTreeChange.objects.filter(backup=obj, file__isnull=False).count(),
    )

    def get_children(self, request, parent):
        return self.child_model.objects.filter(backup=parent, file__isnull=False)

    def get_extra_context(self, request, instance):
        return {
            'running': bool(request.GET.get('type') == 'running'),
            'startup': bool(request.GET.get('type') == 'startup'),
        }




@register_model_view(Backup, 'edit')
class BackupEditView(ObjectEditView):
    queryset = Backup.objects.all()
    form = BackupForm


@register_model_view(Backup, 'delete')
class BackupDeleteView(ObjectDeleteView):
    queryset = Backup.objects.all()

    def get_return_url(self, request, obj=None):

        # First, see if `return_url` was specified as a query parameter or form data. Use this URL only if it's
        # considered safe.
        return_url = request.GET.get('return_url') or request.POST.get('return_url')
        if return_url and return_url.startswith('/'):
            return return_url

        # Next, check if the object being modified (if any) has an absolute URL.
        if obj is not None and obj.pk and hasattr(obj, 'get_absolute_url'):
            return obj.get_absolute_url()

        # Fall back to the default URL (if specified) for the view.
        if self.default_return_url is not None:
            return reverse(self.default_return_url)

        # Attempt to dynamically resolve the list view for the object
        if hasattr(self, 'queryset'):
            model_opts = self.queryset.model._meta
            try:
                return reverse(f'plugins:{model_opts.app_label}:{model_opts.model_name}_list')
            except NoReverseMatch:
                pass

        # If all else fails, return home. Ideally this should never happen.
        return reverse('home')


@register_model_view(Backup, 'config')
class ConfigView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/config.html'
    tab = ViewTab(
        label='Configuration',
    )

    def get(self, request, pk, current=None):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        if current:
            current = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=current)
        else:
            current = BackupCommitTreeChange.objects.filter(backup=backup, file__isnull=False).last()
            if not current:
                raise Http404(
                    "No current commit available"
                )

        path = f'{current.file.path}'

        repo = GitBackup()
        config = repo.read(path, current.commit.sha)

        previous = None
        if current is not None and current.old is not None:
            try:
                previous = backup.changes.filter(file__type=current.file.type, commit__time__lt=current.commit.time).\
                    last()
            except:
                pass

        return render(request, 'netbox_config_backup/config.html', {
            'object': backup,
            'tab': self.tab,
            'backup_config': config,
            'current': current,
            'previous': previous,
            'active_tab': 'config',
        })


@register_model_view(Backup, 'diff')
class DiffView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/diff.html'
    tab = ViewTab(
        label='Diff',
    )

    def get(self, request, pk, current=None, previous=None):
        backup = get_object_or_404(Backup.objects.all(), pk=pk)
        if current:
            current = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=current)
        else:
            current = BackupCommitTreeChange.objects.filter(backup=backup, file__isnull=False).last()
            if not current:
                raise Http404(
                    "No current commit available"
                )
        if previous:
            previous = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=previous)
        else:
            previous = BackupCommitTreeChange.objects.filter(
                backup=backup,
                file__type=current.file.type,
                commit__time__lt=current.commit.time
            ).last()
            if not previous:
                raise Http404(
                    "No Previous Commit"
                )

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
            'tab': self.tab,
            'diff': diff,
            'current': current,
            'previous': previous,
            'active_tab': 'diff',
        })
