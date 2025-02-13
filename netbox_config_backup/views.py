import logging

from django.contrib import messages
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, NoReverseMatch
from django.utils.translation import gettext as _
from django.views import View
from jinja2 import TemplateError

from core.choices import JobStatusChoices
from dcim.models import Device
from netbox.views.generic import ObjectDeleteView, ObjectEditView, ObjectView, ObjectListView, ObjectChildrenView, \
    BulkEditView, BulkDeleteView
from netbox_config_backup.filtersets import BackupFilterSet, BackupsFilterSet, BackupJobFilterSet

from netbox_config_backup.forms import BackupForm, BackupFilterSetForm, BackupBulkEditForm, BackupJobFilterSetForm
from netbox_config_backup.git import GitBackup
from netbox_config_backup.models import Backup, BackupJob, BackupCommitTreeChange, BackupCommit, BackupObject
from netbox_config_backup.tables import BackupTable, BackupsTable, BackupJobTable
from netbox_config_backup.utils import get_backup_tables, Differ
from utilities.views import register_model_view, ViewTab

logger = logging.getLogger(f"netbox_config_backup")


class BackupJobListView(ObjectListView):
    queryset = BackupJob.objects.all()

    filterset = BackupJobFilterSet
    filterset_form = BackupJobFilterSetForm
    table = BackupJobTable
    action_buttons = ()


class BackupListView(ObjectListView):
    queryset = Backup.objects.filter(device__isnull=False).default_annotate()

    filterset = BackupFilterSet
    filterset_form = BackupFilterSetForm
    table = BackupTable
    action_buttons = ('add', )


class UnassignedBackupListView(ObjectListView):
    queryset = Backup.objects.filter(device__isnull=True).default_annotate()

    filterset = BackupFilterSet
    filterset_form = BackupFilterSetForm
    table = BackupTable
    action_buttons = ()


@register_model_view(Backup)
class BackupView(ObjectView):
    queryset = Backup.objects.all().default_annotate()
    template_name = 'netbox_config_backup/backup.html'

    def get_extra_context(self, request, instance):

        jobs = BackupJob.objects.filter(backup=instance).order_by()
        is_running = True if jobs.filter(status=JobStatusChoices.STATUS_RUNNING).count() > 0 else False
        is_pending = True if jobs.filter(status=JobStatusChoices.STATUS_PENDING).count() > 0 else False

        job_status = None
        if is_pending:
            job_status = 'Pending'
        if is_running:
            job_status = 'Running'

        status = {
            'status': job_status,
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
    queryset = Backup.objects.all().default_annotate()

    template_name = 'netbox_config_backup/backups.html'
    child_model = BackupCommitTreeChange
    table = BackupsTable
    filterset = BackupsFilterSet
    actions = {
        'config': {'view'},
        'diff': {'view'},
        'bulk_diff': {'view'}
    }
    tab = ViewTab(
        label='View Backups',
        badge=lambda obj: BackupCommitTreeChange.objects.filter(backup=obj, file__isnull=False).count(),
    )

    def get_children(self, request, parent):
        return self.child_model.objects.filter(backup=parent, file__isnull=False)

    def get_extra_context(self, request, instance):
        return {
            'backup': instance,
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


@register_model_view(Backup, 'bulk_edit')
class BackupBulkEditView(BulkEditView):
    queryset = Backup.objects.all()
    form = BackupBulkEditForm
    filterset = BackupFilterSet
    table = BackupTable


@register_model_view(Backup, 'bulk_delete')
class BackupBulkDeleteView(BulkDeleteView):
    queryset = Backup.objects.all()
    filterset = BackupFilterSet
    table = BackupTable


@register_model_view(Backup, 'config')
class ConfigView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/config.html'
    tab = ViewTab(
        label='Configuration',
    )

    def get(self, request, backup, current=None):
        backup = get_object_or_404(Backup.objects.all(), pk=backup)
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


@register_model_view(Backup, 'compliance')
class ComplianceView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/compliance.html'
    tab = ViewTab(
        label='Compliance',
        weight=500,
    )

    def get_rendered_config(self, request, backup):
        instance = backup.device
        config_template = instance.get_config_template()
        context_data = instance.get_config_context()
        context_data.update({'device': instance})
        try:
            rendered_config = config_template.render(context=context_data)
        except TemplateError as e:
            messages.error(request, _("An error occurred while rendering the template: {error}").format(error=e))
            rendered_config = ''
        return rendered_config

    def get_current_backup(self, current, backup):
        if current:
            current = get_object_or_404(BackupCommitTreeChange.objects.all(), pk=current)
        else:
            current = BackupCommitTreeChange.objects.filter(backup=backup, file__isnull=False).last()
            if not current:
                raise Http404(
                    "No current commit available"
                )
        repo = GitBackup()
        current_sha = current.commit.sha if current.commit is not None else 'HEAD'
        current_config = repo.read(current.file.path, current_sha)

    def get_diff(self, backup, rendered, current):
        if backup.device and backup.device.platform.napalm.napalm_driver in ['ios', 'nxos']:
            differ = Differ(rendered, current)
            diff = differ.cisco_compare()
        else:
            differ = Differ(rendered, current)
            diff = differ.compare()

        for idx, line in enumerate(diff):
            diff[idx] = line.rstrip()
        return diff


    def get(self, request, backup, current=None, previous=None):
        backup = get_object_or_404(Backup.objects.all(), pk=backup)

        diff = ['No rendered configuration', ]
        rendered_config = None
        if backup.device and backup.device.get_config_template():
            rendered_config = self.get_rendered_config(request=request, backup=backup)
            current_config = self.get_current_backup(backup=backup, current=current)
            if rendered_config:
                diff = self.get_diff(backup=backup, rendered=rendered_config, current=current_config)

        return render(request, self.template_name, {
            'object': backup,
            'tab': self.tab,
            'diff': diff,
            'current': current,
            'active_tab': 'compliance',
        })


@register_model_view(Backup, 'diff')
class DiffView(ObjectView):
    queryset = Backup.objects.all()
    template_name = 'netbox_config_backup/diff.html'
    tab = ViewTab(
        label='Diff',
    )

    def post(self, request, backup, *args, **kwargs):
        if request.POST.get('_all') and self.filterset is not None:
            queryset = self.filterset(request.GET, self.parent_model.objects.only('pk'), request=request).qs
            pk_list = [obj.pk for obj in queryset]
        else:
            pk_list = [int(pk) for pk in request.POST.getlist('pk')]

        backups = pk_list[:2]

        if len(backups) == 2:
            current = int(backups[0])
            previous = int(backups[1])
        elif len(backups) == 1:
            current = int(backups[0])
            previous = None
        else:
            current = None
            previous = None

        return self.get(request=request, backup=backup, current=current, previous=previous)

    def get(self, request, backup, current=None, previous=None):
        backup = get_object_or_404(Backup.objects.all(), pk=backup)
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

        repo = GitBackup()

        previous_sha = previous.commit.sha if previous.commit is not None else 'HEAD'
        current_sha = current.commit.sha if current.commit is not None else None

        if backup.device and backup.device.platform.napalm.napalm_driver in ['ios', 'nxos']:
            new = repo.read(current.file.path, current_sha)
            old = repo.read(previous.file.path, previous_sha)
            differ = Differ(old, new)
            diff = differ.cisco_compare()
        else:
            new = repo.read(current.file.path, current_sha)
            old = repo.read(previous.file.path, previous_sha)
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


@register_model_view(Device, name='backups')
class DeviceBackupsView(ObjectChildrenView):
    queryset = Device.objects.all()

    template_name = 'netbox_config_backup/backups.html'
    child_model = BackupCommitTreeChange
    table = BackupsTable
    filterset = BackupsFilterSet
    actions = {
        'config': {'view'},
        'diff': {'view'},
        'bulk_diff': {'view'}
    }
    tab = ViewTab(
        label='Backups',
        weight=100,
        badge=lambda obj: BackupCommitTreeChange.objects.filter(backup__device=obj, file__isnull=False).count(),
    )

    def get_children(self, request, parent):
        return self.child_model.objects.filter(backup__device=parent, file__isnull=False)

    def get_extra_context(self, request, instance):
        return {
            'backup': instance.backups.filter(status='active').last(),
            'running': bool(request.GET.get('type') == 'running'),
            'startup': bool(request.GET.get('type') == 'startup'),
        }
