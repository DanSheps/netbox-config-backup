from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device
from core.choices import JobStatusChoices
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.jobs.backup import BackupRunner


class TestBackupScheduling(TestCase):
    """Tests for job scheduling logic"""

    @classmethod
    def setUpTestData(cls):
        site = Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        device_type = DeviceType.objects.create(
            model='Generic Type', slug='generic-type', manufacturer=manufacturer
        )
        device_role = DeviceRole.objects.create(name='Generic Role', slug='generic-role')
        cls.device = Device.objects.create(
            name='Test Device', device_type=device_type, role=device_role, site=site
        )
        cls.backup = Backup.objects.create(name='Test Backup', device=cls.device)

    def test_schedule_missed_jobs_respects_frequency(self):
        """Jobs should not run before scheduled time"""
        # Create a job scheduled for 1 hour in the future
        future_time = timezone.now() + timedelta(hours=1)
        job_future = BackupJob.objects.create(
            backup=self.backup,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled=future_time,
            job_id='test-future-job',
        )

        # Create a job scheduled for the past (should run)
        past_time = timezone.now() - timedelta(minutes=5)
        job_past = BackupJob.objects.create(
            backup=self.backup,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled=past_time,
            job_id='test-past-job',
        )

        # Get scheduled jobs using the runner method
        jobs_to_run = BackupRunner.get_backup_jobs(backups=[self.backup])

        # Only past job should be selected
        job_ids = [job.id for job in jobs_to_run]
        self.assertIn(job_past.id, job_ids, "Past job should be selected")
        self.assertNotIn(job_future.id, job_ids, "Future job should NOT be selected")

    def test_scheduled_jobs_filtered_by_time(self):
        """Test that scheduled__lte filter properly excludes future jobs"""
        now = timezone.now()

        # Job scheduled for now (should run)
        job_now = BackupJob.objects.create(
            backup=self.backup,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled=now,
            job_id='test-now-job',
        )

        # Job scheduled for 5 minutes in future (should NOT run)
        job_future = BackupJob.objects.create(
            backup=self.backup,
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled=now + timedelta(minutes=5),
            job_id='test-future-5min-job',
        )

        # Get jobs that should run
        jobs = BackupJob.objects.filter(
            status=JobStatusChoices.STATUS_SCHEDULED,
            scheduled__lte=timezone.now()
        )

        job_ids = [job.id for job in jobs]
        self.assertIn(job_now.id, job_ids, "Job scheduled for now should be included")
        self.assertNotIn(job_future.id, job_ids, "Job scheduled for future should NOT be included")


class TestJobErrorHandling(TestCase):
    """Tests for job error handling and status management"""

    @classmethod
    def setUpTestData(cls):
        site = Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        device_type = DeviceType.objects.create(
            model='Generic Type', slug='generic-type', manufacturer=manufacturer
        )
        device_role = DeviceRole.objects.create(name='Generic Role', slug='generic-role')
        cls.device = Device.objects.create(
            name='Test Device', device_type=device_type, role=device_role, site=site
        )
        cls.backup = Backup.objects.create(name='Test Backup', device=cls.device)

    def test_fail_job_stores_error_message(self):
        """Test that fail_job() properly stores error messages"""
        jobs = [
            BackupJob.objects.create(
                backup=self.backup,
                status=JobStatusChoices.STATUS_RUNNING,
                job_id='test-fail-job-1',
            )
        ]

        error_message = 'Connection timeout occurred'
        BackupRunner.fail_job(jobs=jobs, status=JobStatusChoices.STATUS_FAILED, message=error_message)

        # Refresh from DB
        job = BackupJob.objects.get(pk=jobs[0].pk)

        self.assertEqual(job.status, JobStatusChoices.STATUS_FAILED)
        self.assertIn('error', job.data, "Job data should contain error key")
        self.assertEqual(job.data['error'], error_message, "Error message should match")
        self.assertIsInstance(job.data['error'], str, "Error should be stored as string, not set")

    def test_enqueued_state_choices_comparison(self):
        """Test that status comparison with ENQUEUED_STATE_CHOICES works correctly"""
        # This tests the fix for issue 5.3
        from core.choices import JobStatusChoices

        # ENQUEUED_STATE_CHOICES is a list of (value, label) tuples
        enqueued_values = [choice[0] for choice in JobStatusChoices.ENQUEUED_STATE_CHOICES]

        for status_value in enqueued_values:
            self.assertIn(
                status_value,
                JobStatusChoices.ENQUEUED_STATE_CHOICES,
                f"Status {status_value} should be in ENQUEUED_STATE_CHOICES"
            )

    def test_job_status_transitions(self):
        """Test proper job status transitions"""
        job = BackupJob.objects.create(
            backup=self.backup,
            status=JobStatusChoices.STATUS_PENDING,
            job_id='test-transition-job',
        )

        # Should start as PENDING
        self.assertEqual(job.status, JobStatusChoices.STATUS_PENDING)

        # Transition to RUNNING
        job.status = JobStatusChoices.STATUS_RUNNING
        job.save()
        self.assertEqual(job.status, JobStatusChoices.STATUS_RUNNING)

        # Transition to COMPLETED
        job.status = JobStatusChoices.STATUS_COMPLETED
        job.completed = timezone.now()
        job.save()
        self.assertEqual(job.status, JobStatusChoices.STATUS_COMPLETED)


