from django import forms
from django.core.exceptions import ValidationError
from django.forms import CharField
from django.utils.translation import gettext as _

from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from ipam.models import IPAddress
from netbox_config_backup.models import Backup
from utilities.forms import BootstrapMixin
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField

__all__ = (
    'BackupForm',
    'BackupFilterSetForm',
)


class BackupForm(BootstrapMixin, forms.ModelForm):
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
    class Meta:
        model = Backup
        fields = ('name', 'device', 'ip', 'status')

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


class BackupFilterSetForm(BootstrapMixin, forms.Form):
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
        fetch_trigger='open',
        query_params={
            'status': [DeviceStatusChoices.STATUS_ACTIVE],
            'platform__napalm__ne': None,
            'has_primary_ip': True,
        }
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


