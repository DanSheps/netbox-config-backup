import logging

from django.db import models
from django.db.models import ForeignKey
from django.utils import timezone
from django_rq import get_queue
from extras.choices import JobResultStatusChoices
from .abstract import BigIDModel

logger = logging.getLogger(f"netbox_config_backup")


class BackupJob(BigIDModel):
    backup = ForeignKey(
        to='Backup',
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        related_name='jobs',
    )
    created = models.DateTimeField(
        auto_now_add=True
    )
    scheduled = models.DateTimeField(
        null=True,
        blank=True
    )
    started = models.DateTimeField(
        null=True,
        blank=True
    )
    completed = models.DateTimeField(
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=30,
        choices=JobResultStatusChoices,
        default=JobResultStatusChoices.STATUS_PENDING
    )
    data = models.JSONField(
        null=True,
        blank=True
    )
    job_id = models.UUIDField(
        unique=True
    )

    def __str__(self):
        return str(self.job_id)

    def delete(self, using=None, keep_parents=False):
        queue = get_queue('netbox_config_backup.jobs')

        queue.fetch_job(f'{self.job_id}').cancel()
        queue.fetch_job(f'{self.job_id}').remove()

        super().delete(using=using, keep_parents=keep_parents)

    @property
    def duration(self):
        if not self.completed:
            return None

        duration = self.completed - self.started
        minutes, seconds = divmod(duration.total_seconds(), 60)

        return f"{int(minutes)} minutes, {seconds:.2f} seconds"

    def set_status(self, status):
        """
        Helper method to change the status of the job result. If the target status is terminal, the  completion
        time is also set.
        """
        self.status = status
        if status in JobResultStatusChoices.TERMINAL_STATE_CHOICES:
            self.completed = timezone.now()

    def reschedule(self, time):
        """
        Reschedule a job
        """
        if self.status == JobResultStatusChoices.STATUS_PENDING:
            self.scheduled = time()
        else:
            raise Exception('Job is not in a state for rescheduling')

    @classmethod
    def enqueue(cls, backup, delay=None):
        from netbox_config_backup.utils import enqueue
        enqueue(backup, delay)

    @classmethod
    def enqueue_if_needed(cls, backup, delay=None, job_id=None):
        from netbox_config_backup.utils import enqueue_if_needed
        enqueue_if_needed(backup, delay, job_id)

    @classmethod
    def needs_enqueue(cls, backup, job_id=None):
        from netbox_config_backup.utils import needs_enqueue
        needs_enqueue(backup, job_id)

    @classmethod
    def is_running(cls, backup, job_id=None):
        from netbox_config_backup.utils import is_running
        is_running(backup, job_id)

    @classmethod
    def is_queued(cls, backup, job_id=None):
        from netbox_config_backup.utils import is_queued
        is_queued(backup, job_id)

    @classmethod
    def remove_orphaned(cls):
        from netbox_config_backup.utils import remove_orphaned
        remove_orphaned()

    @classmethod
    def remove_queued(cls, backup):
        from netbox_config_backup.utils import remove_queued
        remove_queued()