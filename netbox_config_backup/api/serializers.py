from rest_framework import serializers

from dcim.api.serializers import DeviceSerializer
from ipam.api.serializers import IPAddressSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_config_backup.models import Backup


__all__ = (
    'BackupSerializer',
)


class BackupSerializer(NetBoxModelSerializer):
    device = DeviceSerializer(nested=True, required=False, allow_null=True),
    ip = IPAddressSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = Backup
        fields = [
            'id', 'url', 'display', 'name', 'device', 'ip',
            'uuid', 'status', 'config_status',
        ]
        brief_fields = ('display', 'id', 'name', 'url')
