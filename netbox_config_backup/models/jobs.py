import logging

from django.db import models
from django.db.models import ForeignKey
from django.utils import timezone
from django.utils.translation import gettext as _

from django_rq import get_queue

from core.choices import JobStatusChoices
from netbox.models import NetBoxModel
from utilities.querysets import RestrictedQuerySet
from .abstract import BigIDModel

logger = logging.getLogger(f"netbox_config_backup")


class BackupJob(NetBoxModel):
    runner = models.ForeignKey(
        verbose_name=_('Job Run'),
        to='core.Job',
        on_delete=models.SET_NULL,
        related_name='backup_job',
        null=True,
        blank=True
    )
    backup = ForeignKey(
        to='Backup',
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        related_name='jobs',
    )
    pid = models.BigIntegerField(
        verbose_name=_('PID'),
        null=True,
        blank=True,
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
        choices=JobStatusChoices,
        default=JobStatusChoices.STATUS_PENDING
    )
    data = models.JSONField(
        null=True,
        blank=True
    )
    job_id = models.UUIDField(
        unique=True
    )

    objects = RestrictedQuerySet.as_manager()

    def __str__(self):
        return str(self.job_id)

    @property
    def queue(self):
        return get_queue('netbox_config_backup.jobs')

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
        if status in JobStatusChoices.TERMINAL_STATE_CHOICES:
            self.completed = timezone.now()