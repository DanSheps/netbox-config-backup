import logging

import uuid
from django.utils import timezone
from django_rq import get_queue
from rq.registry import ScheduledJobRegistry

from dcim.choices import DeviceStatusChoices
from extras.choices import JobResultStatusChoices
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models.jobs import BackupJob

logger = logging.getLogger(f"netbox_config_backup")


def enqueue(backup, delay=None):
    from netbox_config_backup.models import BackupJob

    scheduled = timezone.now()
    if delay is not None:
        logger.info(f'{backup}: Scheduling for: {scheduled + delay} at {scheduled} ')
        scheduled = timezone.now() + delay

    result = BackupJob.objects.create(
        backup=backup,
        job_id=uuid.uuid4(),
        scheduled=scheduled,
    )
    queue = get_queue('netbox_config_backup.jobs')
    if delay is None:
        logger.debug(f'{backup}: Enqueued')
        job = queue.enqueue(
            'netbox_config_backup.tasks.backup_job',
            description=f'{backup.uuid}',
            job_id=str(result.job_id),
            pk=result.pk,
        )
        logger.info(f'{backup}: {result.job_id}')
    else:
        logger.debug(f'{backup}: Enqueued')
        job = queue.enqueue_in(
            delay,
            'netbox_config_backup.tasks.backup_job',
            description=f'{backup.uuid}',
            job_id=str(result.job_id),
            pk=result.pk
        )
        logger.info(f'{backup}: {result.job_id}')

    return job


def enqueue_if_needed(backup, delay=None, job_id=None):
    if needs_enqueue(backup, job_id=job_id):
        return enqueue(backup, delay=delay)
    return False


def needs_enqueue(backup, job_id=None):
    queue = get_queue('netbox_config_backup.jobs')
    scheduled = queue.scheduled_job_registry
    started = queue.started_job_registry

    scheduled_jobs = scheduled.get_job_ids()
    started_jobs = started.get_job_ids()

    if backup.device is None:
        print(f'No device for {backup}')
        return False
    elif backup.status == StatusChoices.STATUS_DISABLED:
        print(f'Backup disabled for {backup}')
        return False
    elif backup.device.status in [DeviceStatusChoices.STATUS_OFFLINE,
                                DeviceStatusChoices.STATUS_FAILED,
                                DeviceStatusChoices.STATUS_INVENTORY,
                                DeviceStatusChoices.STATUS_PLANNED]:
        print(f'Backup disabled for {backup} due to device status ({backup.device.status})')
        return False
    elif (backup.ip is None and backup.device.primary_ip is None) or backup.device.platform is None or \
            backup.device.platform.napalm_driver == '' or backup.device.platform.napalm_driver is None:
        print(f'Backup disabled for {backup} due to napalm drive or no primary IP ({backup.device.status})')
        return False
    elif is_queued(backup, job_id):
        print(f'Backup already queued for {backup}')
        return False

    return True


def is_running(backup, job_id=None):
    queue = get_queue('netbox_config_backup.jobs')

    jobs = backup.jobs.all()
    queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING])

    if job_id is not None:
        queued.exclude(job_id=job_id)

    for backupjob in queued.all():
        job = queue.fetch_job(f'{backupjob.job_id}')
        if job and job.is_started and job.id in queue.started_job_registry.get_job_ids() + queue.get_job_ids():
            return True
        elif job and job.is_started and job.id not in queue.started_job_registry.get_job_ids():
            status = {
                     'is_canceled': job.is_canceled,
                     'is_deferred': job.is_deferred,
                     'is_failed': job.is_failed,
                     'is_finished': job.is_finished,
                     'is_queued': job.is_queued,
                     'is_scheduled': job.is_scheduled,
                     'is_started': job.is_started,
                     'is_stopped': job.is_stopped,
            }
            job.cancel()
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
            logger.warning(f'{backup}: Job in started queue but not in a registry, cancelling {status}')
        elif job and job.is_canceled:
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
    return False


def get_scheduled(backup, job_id=None):
    queue = get_queue('netbox_config_backup.jobs')

    scheduled_jobs = queue.scheduled_job_registry.get_job_ids()
    started_jobs = queue.started_job_registry.get_job_ids()
    queued_jobs = queue.get_job_ids()

    jobs = backup.jobs.all()
    queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])

    if job_id is not None:
        queued.exclude(job_id=job_id)

    for backupjob in queued.all():
        job = queue.fetch_job(f'{backupjob.job_id}')
        if job and (job.is_scheduled or job.is_queued) and job.id in scheduled_jobs + started_jobs + queued_jobs:
            if job.enqueued_at is not None:
                return job.enqueued_at
            else:
                return queue.scheduled_job_registry.get_scheduled_time(job)
        elif job and (job.is_scheduled or job.is_queued) and job.id not in scheduled_jobs + started_jobs:
            status = {
                     'is_canceled': job.is_canceled,
                     'is_deferred': job.is_deferred,
                     'is_failed': job.is_failed,
                     'is_finished': job.is_finished,
                     'is_queued': job.is_queued,
                     'is_scheduled': job.is_scheduled,
                     'is_started': job.is_started,
                     'is_stopped': job.is_stopped,
            }
            job.cancel()
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
            logger.warning(f'{backup}: Job in scheduled or started queue but not in a registry, cancelling {status} {scheduled_jobs + started_jobs + queued_jobs}')
        elif job and job.is_canceled:
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
    return None


def is_queued(backup, job_id=None):
    if get_scheduled(backup, job_id) is not None:
        return True
    return False


def remove_orphaned():
    queue = get_queue('netbox_config_backup.jobs')
    registry = ScheduledJobRegistry(queue=queue)

    for job_id in registry.get_job_ids():
        try:
            BackupJob.objects.get(job_id=job_id)
        except BackupJob.DoesNotExist:
            registry.remove(job_id)


def remove_queued(backup):
    queue = get_queue('netbox_config_backup.jobs')
    registry = ScheduledJobRegistry(queue=queue)
    for job_id in registry.get_job_ids():
        job = queue.fetch_job(f'{job_id}')
        if job.description == f'{backup.uuid}':
            registry.remove(f'{job_id}')
