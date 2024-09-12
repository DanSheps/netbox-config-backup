from django.test import TestCase

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device
from ipam.models import IPAddress
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_config_backup.filtersets import BackupFilterSet
from netbox_config_backup.models import Backup



class BackupTestCase(TestCase):
    queryset = Backup.objects.all()
    filterset = BackupFilterSet

    @classmethod
    def setUpTestData(cls):
        site = Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model='Device Type 1', slug='device-type-1'
        )
        role = DeviceRole.objects.create(
            name='Device Role 1', slug='device-role-1'
        )

        ip = IPAddress.objects.create(
            address='10.10.10.10/32'
        )

        devices = (
            Device(name='Device 1', device_type=device_type, role=role, site=site),
            Device(name='Device 2', device_type=device_type, role=role, site=site),
        )
        Device.objects.bulk_create(devices)

        backups = (
            Backup(name='Backup 1', device=devices[0]),
            Backup(name='Backup 2', device=devices[1]),
            Backup(name='Backup 3', device=devices[1], ip=ip),
        )
        Backup.objects.bulk_create(backups)

    def test_q(self):
        params = {'q': 'Backup 1'}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_name(self):
        params = {'name': ['Backup 1', 'Backup 2']}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_device(self):
        params = {'device': ['Device 2']}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_ip(self):
        params = {'ip_address': ['10.10.10.10']}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)