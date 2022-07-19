from django import forms
from django.forms import CharField
from django.utils.translation import gettext as _

from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from ipam.models import IPAddress
from netbox_config_backup.models import Backup
from utilities.forms import BootstrapMixin, DynamicModelChoiceField

__all = (
    'VirtualCircuitForm',
    'VirtualCircuitInterfaceForm',
)


class BackupForm(BootstrapMixin, forms.ModelForm):
    device = DynamicModelChoiceField(
        label='Device',
        required=False,
        queryset=Device.objects.all(),
        query_params={
            'status': [DeviceStatusChoices.STATUS_ACTIVE],
            'platform__napalm__ne': None,
            'has_primary_ip': True,
        },
    )
    ip = DynamicModelChoiceField(
        label='IP Address',
        required=False,
        queryset=IPAddress.objects.all(),
        query_params={
            'device_id': '$device'
        }
    )
    class Meta:
        model = Backup
        fields = ('name', 'device', 'ip')

    def clean(self):
        super().clean()
        if self.cleaned_data.get('device', None) == None:
            self.cleaned_data['ip'] = None


class BackupFiltersetForm(BootstrapMixin, forms.Form):
    model = Backup
    field_order = [
        'q', 'name', 'device'
    ]
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('All Fields')}),
        label=_('Search')
    )


