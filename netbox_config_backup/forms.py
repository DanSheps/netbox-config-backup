from django import forms
from django.core.exceptions import ValidationError
from django.forms import CharField
from django.utils.translation import gettext as _

from core.choices import JobStatusChoices
from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from ipam.models import IPAddress
from netbox.forms import NetBoxModelForm, NetBoxModelBulkEditForm
from netbox_config_backup.models import Backup, BackupJob
from utilities.forms import add_blank_choice
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField, CommentField

__all__ = (
    'BackupForm',
    'BackupJobFilterSetForm',
    'BackupFilterSetForm',
    'BackupBulkEditForm',
)

from utilities.forms.rendering import FieldSet


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
        query_params={
            'device_id': '$device',
            'assigned_to_interface': True
        },
    )
    comments = CommentField()

    class Meta:
        model = Backup
        fields = ('name', 'device', 'ip', 'status', 'description', 'comments', 'config_status')

    def clean(self):
        super().clean()
        if self.cleaned_data.get('ip') and not self.cleaned_data.get('device'):
            raise ValidationError({'ip': f'Device must be set'})

        if self.cleaned_data.get('device'):
            device = self.cleaned_data.get('device')
            if not device.platform:
                raise ValidationError({'device': f'{device} has no platform set'})
            elif not hasattr(device.platform, 'napalm'):
                raise ValidationError({'device': f'{device}\'s platform ({device.platform}) has no napalm driver'})


class BackupJobFilterSetForm(forms.Form):
    model = BackupJob
    field_order = [
        'q', 'status',
    ]
    status = forms.MultipleChoiceField(
        required=False,
        choices=add_blank_choice(JobStatusChoices),
        label=_('Status')
    )


class BackupFilterSetForm(forms.Form):
    model = Backup
    field_order = [
        'q', 'name', 'device_id', 'ip'
    ]
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('All Fields')}),
        label=_('Search')
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
        label=_('IP Address')
    )


class BackupBulkEditForm(NetBoxModelBulkEditForm):

    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    comments = CommentField()

    model = Backup
    fieldsets = ()
    nullable_fields = ()
