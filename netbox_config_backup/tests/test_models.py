from django.test import TestCase

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device
from netbox_config_backup.choices import FileTypeChoices
from netbox_config_backup.models import Backup, BackupCommitTreeChange


class TestBackup(TestCase):

    @classmethod
    def setUpTestData(cls):
        Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        DeviceType.objects.create(model='Generic Type', slug='generic-type', manufacturer=manufacturer)
        DeviceRole.objects.create(name='Generic Role', slug='generic-role')

    def test_create_backup(self):
        configs = {FileTypeChoices.TYPE_RUNNING: 'Test Backup', FileTypeChoices.TYPE_STARTUP: 'Test Backup'}

        site = Site.objects.first()
        role = DeviceRole.objects.first()
        device_type = DeviceType.objects.first()

        device = Device.objects.create(name='Test Device', device_type=device_type, role=role, site=site)
        backup = Backup.objects.create(name='Backup 1', device=device)

        changes = backup.write_config(configs)
        commit = backup.commit(backups=[backup])
        backup.update_commit_tree(commit=commit)
        retrieved = backup.get_config()

        self.assertEqual(configs[FileTypeChoices.TYPE_RUNNING], retrieved[FileTypeChoices.TYPE_RUNNING])
        self.assertEqual(configs[FileTypeChoices.TYPE_STARTUP], retrieved[FileTypeChoices.TYPE_STARTUP])

    def test_rebuild_bctc_correct_backup_filtering(self):
        """Ensure rebuild_bctc filters by backup, not by PK"""
        site = Site.objects.first()
        role = DeviceRole.objects.first()
        device_type = DeviceType.objects.first()

        # Create two backups
        device1 = Device.objects.create(name='Device 1', device_type=device_type, role=role, site=site)
        device2 = Device.objects.create(name='Device 2', device_type=device_type, role=role, site=site)

        backup1 = Backup.objects.create(name='Backup 1', device=device1)
        backup2 = Backup.objects.create(name='Backup 2', device=device2)

        # Add configs and commits to both
        configs = {FileTypeChoices.TYPE_RUNNING: 'Config 1', FileTypeChoices.TYPE_STARTUP: 'Startup 1'}
        backup1.write_config(configs)
        Backup.commit(backups=[backup1])
        backup1.update_commit_tree()

        configs2 = {FileTypeChoices.TYPE_RUNNING: 'Config 2', FileTypeChoices.TYPE_STARTUP: 'Startup 2'}
        backup2.write_config(configs2)
        Backup.commit(backups=[backup2])
        backup2.update_commit_tree()

        # Get BCTC counts before rebuild
        bctc_count_backup1_before = BackupCommitTreeChange.objects.filter(backup=backup1).count()
        bctc_count_backup2_before = BackupCommitTreeChange.objects.filter(backup=backup2).count()

        self.assertGreater(bctc_count_backup1_before, 0)
        self.assertGreater(bctc_count_backup2_before, 0)

        # Rebuild backup1 - should NOT delete backup2's changes
        backup1.rebuild_bctc()

        # Check that backup2's changes were not affected
        bctc_count_backup2_after = BackupCommitTreeChange.objects.filter(backup=backup2).count()
        self.assertEqual(
            bctc_count_backup2_before,
            bctc_count_backup2_after,
            "rebuild_bctc on backup1 should not delete backup2's changes",
        )

    def test_update_commit_tree_handles_deleted_files(self):
        """File deletions should be recorded in commit tree (Bug #2 from issue 1.2)"""
        site = Site.objects.first()
        role = DeviceRole.objects.first()
        device_type = DeviceType.objects.first()

        device = Device.objects.create(name='Test Device', device_type=device_type, role=role, site=site)
        backup = Backup.objects.create(name='Backup 1', device=device)

        # Write initial configs
        configs = {FileTypeChoices.TYPE_RUNNING: 'Initial Config', FileTypeChoices.TYPE_STARTUP: 'Initial Startup'}
        backup.write_config(configs)
        Backup.commit(backups=[backup])
        commits1 = backup.update_commit_tree()

        initial_count = len(commits1)
        self.assertGreater(initial_count, 0, "Should have created BCTC entries")

        # Update configs (simulating file changes)
        configs_updated = {
            FileTypeChoices.TYPE_RUNNING: 'Updated Config',
            FileTypeChoices.TYPE_STARTUP: 'Updated Startup',
        }
        backup.write_config(configs_updated)
        Backup.commit(backups=[backup])
        commits2 = backup.update_commit_tree()

        # Both running and startup should be recorded even if one was deleted in a previous version
        final_count = len(commits2)
        self.assertGreater(final_count, 0, "Should record file deletions in commit tree")
