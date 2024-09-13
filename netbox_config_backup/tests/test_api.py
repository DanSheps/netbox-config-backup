from django.urls import reverse
from rest_framework import status

from utilities.testing import APIViewTestCases, APITestCase

from netbox_config_backup.models import Backup



class AppTest(APITestCase):
    def test_root(self):
        url = reverse("plugins-api:netbox_config_backup-api:api-root")
        response = self.client.get(f"{url}?format=api", **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BackupTest(APIViewTestCases.APIViewTestCase):
    model = Backup
    view_namespace = "plugins-api:netbox_config_backup"
    brief_fields = ['display', 'id', 'name', 'url']
    create_data = [
        {
            'name': 'Backup 4',
            'config_status': False,
        },
        {
            'name': 'Backup 5',
            'config_status': False,
        },
        {
            'name': 'Backup 6',
            'config_status': False,
        },
    ]

    bulk_update_data = {
        'config_status': True
    }

    @classmethod
    def setUpTestData(cls):

        Backup.objects.create(name='Backup 1')
        Backup.objects.create(name='Backup 2')
        Backup.objects.create(name='Backup 3')
