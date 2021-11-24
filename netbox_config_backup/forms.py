from django import forms
from django.forms import CharField
from django.utils.translation import gettext as _

from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from netbox_config_backup.models import Backup
from utilities.forms import BootstrapMixin, DynamicModelChoiceField

__all = (
    'VirtualCircuitForm',
    'VirtualCircuitInterfaceForm',
)


class BackupForm(BootstrapMixin, forms.ModelForm):
    device = DynamicModelChoiceField(
        label='Device',
        required=True,
        queryset=Device.objects.all(),
        query_params={
            'status': [DeviceStatusChoices.STATUS_ACTIVE],
            'platform__napalm__ne': None,
            'has_primary_ip': True,
        },
    )
    class Meta:
        model = Backup
        fields = ('name', 'device')

    def clean(self):
        #print(self.device)
        super().clean()


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


