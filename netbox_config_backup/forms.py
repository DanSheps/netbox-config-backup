from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from core.choices import JobStatusChoices
from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from ipam.models import IPAddress
from netbox.forms import NetBoxModelForm, NetBoxModelBulkEditForm, NetBoxModelFilterSetForm
from netbox_config_backup.models import Backup, BackupJob
from utilities.forms import add_blank_choice, BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import (
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    CommentField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import DateTimePicker

__all__ = (
    'BackupForm',
    'BackupJobFilterSetForm',
    'BackupFilterSetForm',
    'BackupBulkEditForm',
)


class BackupForm(NetBoxModelForm):
    device = DynamicModelChoiceField(
        label='Device',
        required=False,
        queryset=Device.objects.all(),
        help_text='The device this backup operates on',
        query_params={
            'status': [DeviceStatusChoices.STATUS_ACTIVE],
            'has_primary_ip': True,
        },
    )
    ip = DynamicModelChoiceField(
        label='IP Address',
        required=False,
        queryset=IPAddress.objects.all(),
        help_text='This field requires the device to be set',
        query_params={'device_id': '$device', 'assigned_to_interface': True},
    )
    comments = CommentField()

    class Meta:
        model = Backup
        fields = (
            'name',
            'device',
            'ip',
            'status',
            'description',
            'comments',
            'config_status',
        )

    def clean(self):
        super().clean()
        if self.cleaned_data.get('ip') and not self.cleaned_data.get('device'):
            raise ValidationError({'ip': 'Device must be set'})

        if self.cleaned_data.get('device'):
            device = self.cleaned_data.get('device')
            if not device.platform:
                raise ValidationError({'device': f'{device} has no platform set'})
            elif not hasattr(device.platform, 'napalm'):
                raise ValidationError(
                    {
                        'device': f'{device}\'s platform ({device.platform}) has no napalm driver'
                    }
                )


class BackupJobFilterSetForm(NetBoxModelFilterSetForm):
    model = BackupJob
    fieldsets = (
        FieldSet(
            'q',
            'filter_id',
            'tag',
        ),
        FieldSet(
            'status',
            'backup_id',
        ),
        FieldSet(
            'created',
            'scheduled',
            'started',
            'completed',
            name=_('Dates'),
        ),
    )

    status = forms.MultipleChoiceField(
        required=False, choices=add_blank_choice(JobStatusChoices), label=_('Status')
    )
    backup_id = DynamicModelMultipleChoiceField(
        queryset=Backup.objects.all(),
        required=False,
        label=_('Backup'),
    )
    created = forms.DateTimeField(
        label=_('Created'),
        required=False,
        widget=DateTimePicker
    )
    scheduled = forms.DateTimeField(
        label=_('Scheduled'),
        required=False,
        widget=DateTimePicker
    )
    started = forms.DateTimeField(
        label=_('Started'),
        required=False,
        widget=DateTimePicker
    )
    completed = forms.DateTimeField(
        label=_('Completed'),
        required=False,
        widget=DateTimePicker
    )

    def _get_lookup_choices(self, field):
        FORM_FIELD_LOOKUPS = [
            ('exact', _('is')),
            ('n', _('is not')),
            ('gt', _('after')),
            ('gte', _('on or after')),
            ('lt', _('before')),
            ('lte', _('on or before')),
            ('empty_true', _('is empty')),
            ('empty_false', _('is not empty')),
        ]
        lookups = super()._get_lookup_choices(field)

        if isinstance(field, forms.DateTimeField) and not lookups:
            return FORM_FIELD_LOOKUPS

        return lookups


class BackupFilterSetForm(forms.Form):
    model = Backup
    field_order = ['q', 'name', 'device_id', 'ip']
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('All Fields')}),
        label=_('Search'),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_('Device'),
        query_params={
            'status': [DeviceStatusChoices.STATUS_ACTIVE],
            'platform__napalm__ne': None,
            'has_primary_ip': True,
        },
    )
    ip = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'IP Address',
            }
        ),
        label=_('IP Address'),
    )
    config_status = forms.NullBooleanField(
        required=False,
        label=_('Config Saved'),
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )


class BackupBulkEditForm(NetBoxModelBulkEditForm):

    description = forms.CharField(
        label=_('Description'), max_length=200, required=False
    )
    comments = CommentField()

    model = Backup
    fieldsets = ()
    nullable_fields = ()
