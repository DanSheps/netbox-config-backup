import logging

import uuid
from django.utils import timezone
from django_rq import get_queue
from rq.registry import ScheduledJobRegistry

from dcim.choices import DeviceStatusChoices
from extras.choices import JobResultStatusChoices
from netbox_config_backup.models.jobs import BackupJob

logger = logging.getLogger(f"netbox_config_backup")


def enqueue(backup, delay=None):
    from netbox_config_backup.models import BackupJob

    scheduled = timezone.now()
    if delay is not None:
        logger.info(f'Scheduling for: {scheduled + delay} at {scheduled} ')
        scheduled = timezone.now() + delay

    result = BackupJob.objects.create(
        backup=backup,
        job_id=uuid.uuid4(),
        scheduled=scheduled,
    )
    queue = get_queue('netbox_config_backup.jobs')
    if delay is None:
        logger.debug('Enqueued')
        job = queue.enqueue(
            'netbox_config_backup.tasks.backup_job',
            description=f'{backup.uuid}',
            job_id=str(result.job_id),
            pk=result.pk
        )
        logger.info(result.job_id)
    else:
        logger.debug('Enqueued')
        job = queue.enqueue_in(
            delay,
            'netbox_config_backup.tasks.backup_job',
            description=f'{backup.uuid}',
            job_id=str(result.job_id),
            pk=result.pk
        )
        logger.info(result.job_id)

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
        print('Device')
        return False

    if backup.device.status in [DeviceStatusChoices.STATUS_OFFLINE,
                                DeviceStatusChoices.STATUS_FAILED,
                                DeviceStatusChoices.STATUS_INVENTORY,
                                DeviceStatusChoices.STATUS_PLANNED]:
        print('Status')
        return False

    if (backup.ip is None and backup.device.primary_ip is None) or backup.device.platform is None or \
            backup.device.platform.napalm_driver == '' or backup.device.platform.napalm_driver is None:
        print('Napalm')
        return False

    if is_queued(backup, job_id):
        print('Queued')
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
            job.cancel()
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
            logger.warning(f'Job in queue but not in a registry, cancelling')
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
            job.cancel()
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
            logger.warning(f'Job in queue but not in a registry, cancelling')
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
