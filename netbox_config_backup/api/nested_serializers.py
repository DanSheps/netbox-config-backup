from rest_framework import serializers

from netbox.api.serializers import WritableNestedSerializer
from netbox_config_backup.models import Backup


__all__ = (
    'NestedBackupSerializer',
)


class NestedBackupSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_sync-api:sync-detail')

    class Meta:
        model = Backup
        fields = [
            'id', 'url', 'display', 'status'
        ]
