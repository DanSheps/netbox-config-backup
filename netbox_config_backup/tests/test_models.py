from django.core.exceptions import ValidationError
from django.test import TestCase

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device, Interface
from ipam.models import IPAddress
from netbox_config_backup.models import *

class TestBackup(TestCase):

    @classmethod
    def setUpTestData(cls):

        site = Site.objects.create(name='Site 1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1')
        device_type = DeviceType.objects.create(model='Device Type 1', manufacturer=manufacturer)
        role = DeviceRole.objects.create(name='Switch')
        device = Device.objects.create(
            name='Device 1',
            site=site,
            device_type=device_type,
            role=role,
            status='active'
        )
        interface = Interface.objects.create(name='Interface 1', device=device, type='1000baset')
        address = IPAddress.objects.create(assigned_object=interface, address='10.0.0.1/32')
        device.primary_ip4 = address
        device.save()

    def test_create_backup(self):
        pass
