from netbox.api.viewsets import NetBoxModelViewSet
from netbox_config_backup.api import BackupSerializer
from netbox_config_backup.models import Backup


class BackupViewSet(NetBoxModelViewSet):
    queryset = Backup.objects.all()
    serializer_class = BackupSerializer
