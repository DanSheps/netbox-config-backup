from rest_framework import serializers

from dcim.api.serializers import DeviceSerializer
from ipam.api.serializers import IPAddressSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_config_backup.models import Backup


__all__ = (
    'BackupSerializer',
)


class BackupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_config_backup-api:backup-detail')
    device = DeviceSerializer(nested=True)
    ip = IPAddressSerializer(nested=True)

    class Meta:
        model = Backup
        fields = [
            'id', 'url', 'display', 'device', 'ip', 'name', 'uuid', 'status'
        ]
