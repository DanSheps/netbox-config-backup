from rest_framework import serializers

from dcim.api.nested_serializers import NestedDeviceSerializer
from ipam.api.nested_serializers import NestedIPAddressSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_config_backup.models import Backup


__all__ = (
    'BackupSerializer',
)


class BackupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_sync-api:sync-detail')
    device = NestedDeviceSerializer()
    ip = NestedIPAddressSerializer()

    class Meta:
        model = Backup
        fields = [
            'id', 'url', 'display', 'device', 'ip', 'name', 'uuid', 'status'
        ]
