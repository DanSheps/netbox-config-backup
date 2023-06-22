from rest_framework.viewsets import ModelViewSet

from netbox_config_backup.api import BackupSerializer
from netbox_config_backup.models import Backup


class BackupViewSet(ModelViewSet):
    queryset = Backup.objects.all()
    serializer_class = BackupSerializer