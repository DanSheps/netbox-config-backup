from rest_framework import serializers

from core.api.serializers_.jobs import JobSerializer
from dcim.api.serializers import DeviceSerializer
from ipam.api.serializers import IPAddressSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_config_backup.models import Backup, BackupJob

__all__ = (
    'BackupSerializer',
    'BackupJobSerializer',
)


class BackupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_config_backup-api:backup-detail'
    )
    device = DeviceSerializer(nested=True, required=False, allow_null=True),
    ip = IPAddressSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = Backup
        fields = [
            'id', 'url', 'display', 'name', 'device', 'ip',
            'uuid', 'status', 'config_status',
        ]
        brief_fields = ('display', 'id', 'name', 'url')


class BackupJobSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_config_backup-api:backup-detail'
    )
    runner = JobSerializer(nested=True, required=True, allow_null=False),
    backup = BackupSerializer(nested=True, required=True, allow_null=False)

    class Meta:
        model = BackupJob
        fields = [
            'id', 'url', 'display', 'runner', 'backup', 'pid', 'created', 'scheduled', 'started', 'completed', 'status'
            'data', 'status', 'job_id',
        ]
        brief_fields = ('backup', 'display', 'id', 'runner', 'url')
