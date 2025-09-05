from utilities.testing import ViewTestCases, create_test_device

from netbox_config_backup.models import Backup


class BackupTestCase(
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.CreateObjectViewTestCase,
    ViewTestCases.EditObjectViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.BulkEditObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    # ViewTestCases.BulkImportObjectsViewTestCase,
    model = Backup

    @classmethod
    def setUpTestData(cls):
        devices = (
            create_test_device(name="Device 1"),
            create_test_device(name="Device 2"),
            create_test_device(name="Device 3"),
            create_test_device(name="Device 4"),
        )

        backups = (
            Backup(name="Backup 1", device=devices[0]),
            Backup(name="Backup 2", device=devices[1]),
            Backup(name="Backup 3", device=devices[2]),
        )
        Backup.objects.bulk_create(backups)

        cls.form_data = {'name': 'Backup X', 'status': 'disabled'}

        cls.bulk_edit_data = {
            'description': 'A description',
        }

        """
        cls.csv_data = (
            "name,slug,description",
            "Region 4,region-4,Fourth region",
            "Region 5,region-5,Fifth region",
            "Region 6,region-6,Sixth region",
        )

        cls.csv_update_data = (
            "id,name,description",
            f"{regions[0].pk},Region 7,Fourth region7",
            f"{regions[1].pk},Region 8,Fifth region8",
            f"{regions[2].pk},Region 0,Sixth region9",
        )
        """

    def _get_base_url(self):
        return 'plugins:netbox_config_backup:backup_{}'
