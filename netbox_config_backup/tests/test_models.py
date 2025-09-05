from django.test import TestCase

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device
from netbox_config_backup.models import *


class TestBackup(TestCase):

    @classmethod
    def setUpTestData(cls):
        Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(
            name='Manufacturer 1', slug='manufacturer-1'
        )
        DeviceType.objects.create(
            model='Generic Type', slug='generic-type', manufacturer=manufacturer
        )
        DeviceRole.objects.create(name='Generic Role', slug='generic-role')

    def test_create_backup(self):
        configs = {'running': 'Test Backup', 'startup': 'Test Backup'}

        site = Site.objects.first()
        role = DeviceRole.objects.first()
        device_type = DeviceType.objects.first()

        device = Device.objects.create(
            name='Test Device', device_type=device_type, role=role, site=site
        )
        backup = Backup.objects.create(name='Backup 1', device=device)
        backup.set_config(configs)
        retrieved = backup.get_config()

        self.assertEqual(configs['running'], retrieved['running'])
        self.assertEqual(configs['startup'], retrieved['startup'])
