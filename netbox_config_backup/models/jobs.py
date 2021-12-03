import logging
import uuid as uuid
from datetime import datetime

from django.db import models
from django.db.models import ForeignKey
from django.utils import timezone
from django_rq import get_queue
from rq.registry import StartedJobRegistry, ScheduledJobRegistry

from dcim.choices import DeviceStatusChoices
from extras.choices import JobResultStatusChoices
from netbox.models import BigIDModel
from netbox_config_backup.models.backups import Backup

logger = logging.getLogger(f"netbox_config_backup")


class BackupJob(BigIDModel):
    backup = ForeignKey(
        to=Backup,
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
        jobs = queue.scheduled_job_registry.get_job_ids()
        for job in jobs:
            queue.scheduled_job_registry.remove(job)

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

    @classmethod
    def enqueue(cls, backup, delay=None):

        scheduled = timezone.now()
        if delay is not None:
            #logger.info(f'Scheduling for: {scheduled + delay} at {scheduled} ')
            scheduled = timezone.now() + delay

        result = cls.objects.create(
            backup=backup,
            job_id=uuid.uuid4(),
            scheduled=scheduled,
        )
        queue = get_queue('netbox_config_backup.jobs')
        if delay is None:
            logger.debug('Enqueued')
            job = queue.enqueue(
                'netbox_config_backup.tasks.backup_job',
                description=f'backup-{backup.device.pk}',
                job_id=str(result.job_id),
                pk=result.pk
            )
            logger.info(result.job_id)
        else:
            logger.debug('Enqueued')
            job = queue.enqueue_in(
                delay,
                'netbox_config_backup.tasks.backup_job',
                description=f'backup-{backup.device.pk}',
                job_id=str(result.job_id),
                pk=result.pk
            )
            logger.info(result.job_id)

        return job

    @classmethod
    def enqueue_if_needed(cls, backup, delay=None, job_id=None):
        if cls.needs_enqueue(backup, job_id=job_id):
            cls.enqueue(backup, delay=delay)

    @classmethod
    def needs_enqueue(cls, backup, job_id=None):
        queue = get_queue('netbox_config_backup.jobs')
        scheduled = queue.scheduled_job_registry
        started = queue.started_job_registry

        scheduled_jobs = scheduled.get_job_ids()
        started_jobs = started.get_job_ids()

        if backup.device.status in [DeviceStatusChoices.STATUS_OFFLINE,
                                    DeviceStatusChoices.STATUS_FAILED,
                                    DeviceStatusChoices.STATUS_INVENTORY,
                                    DeviceStatusChoices.STATUS_PLANNED]:
            return False

        if backup.device.primary_ip is None or backup.device.platform is None or \
                backup.device.platform.napalm_driver == '' or backup.device.platform.napalm_driver is None:
            return False

        jobs = cls.objects.filter(backup=backup)
        queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])
        if job_id is not None:
            queued = queued.exclude(job_id=job_id)

        if queued.count() > 0:
            for job in queued.all():
                found_job_id = f'{job.job_id}'
                if queue.fetch_job(f'{job.job_id}') is not None and (f'{job.job_id}' in scheduled_jobs or
                                                                     f'{job.job_id}' in started_jobs):
                    return False
        return True

    @classmethod
    def is_running(cls, backup):
        queue = get_queue('netbox_config_backup.jobs')
        registry = StartedJobRegistry(queue=queue)

        jobs = cls.objects.filter(backup=backup)
        queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])
        if queued.count() > 0:
            for job in queued.all():
                if queue.fetch_job(f'{job.job_id}') is not None:
                    return True
        for job_id in registry.get_job_ids():
            job = queue.fetch_job(f'{job_id}')
            if job.description == f'backup-{backup.device.pk}':
                return True
        return False

    @classmethod
    def is_queued(cls, backup):
        queue = get_queue('netbox_config_backup.jobs')
        registry = ScheduledJobRegistry(queue=queue)

        jobs = cls.objects.filter(backup=backup)
        queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])
        if queued.count() > 0:
            for job in queued.all():
                if queue.fetch_job(f'{job.job_id}') is not None:
                    return True
        for job_id in registry.get_job_ids():
            job = queue.fetch_job(f'{job_id}')
            if job.description == f'backup-{backup.device.pk}':
                return True
        return False

    @classmethod
    def remove_queued(cls, backup):
        queue = get_queue('netbox_config_backup.jobs')
        registry = ScheduledJobRegistry(queue=queue)
        for job_id in registry.get_job_ids():
            job = queue.fetch_job(f'{job.job_id}')
            if job.description == f'backup-{backup.device.pk}':
                registry.remove(f'{job_id}')