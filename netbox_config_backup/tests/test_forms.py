from django.test import TestCase

from dcim.models import Device, Platform
from utilities.testing import create_test_device

from netbox_napalm_plugin.models import NapalmPlatformConfig

from netbox_config_backup.forms import *
from netbox_config_backup.models import *



class BackupTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        platform = Platform.objects.create(name='Cisco IOS', slug='cisco-ios')
        device = create_test_device(name='Device 1', platform=platform)
        NapalmPlatformConfig.objects.create(platform=platform, napalm_driver='cisco_ios')

    def test_backup(self):
        form = BackupForm(data={
            'name': 'New Backup',
            'device': Device.objects.first().pk,
            'status': 'disabled'
        })
        print(form.errors)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.save())
