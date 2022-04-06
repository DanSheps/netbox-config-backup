import difflib
import re
import logging
import uuid as uuid

from django.db.models import Q
from django.utils import timezone
from django_rq import get_queue
from rq.registry import ScheduledJobRegistry

from dcim.choices import DeviceStatusChoices
from extras.choices import JobResultStatusChoices
from netbox_config_backup.models import BackupCommitTreeChange, BackupJob
from netbox_config_backup.tables import BackupsTable

logger = logging.getLogger(f"netbox_config_backup")


class Differ(difflib.Differ):
    def plain_compare(self, a, b):
        """
        Use plain replace instead of fancy replace
        :param a:
        :param b:
        :return:
        """

        cruncher = difflib.SequenceMatcher(self.linejunk, a, b)
        for tag, alo, ahi, blo, bhi in cruncher.get_opcodes():
            if tag == 'replace':
                g = self._plain_replace(a, alo, ahi, b, blo, bhi)
            elif tag == 'delete':
                g = self._dump('-', a, alo, ahi)
            elif tag == 'insert':
                g = self._dump('+', b, blo, bhi)
            elif tag == 'equal':
                g = self._dump(' ', a, alo, ahi)
            else:
                raise ValueError('unknown tag %r' % (tag,))

            yield from g

    def cisco_compare(self, a, b, text=True):
        diff = list(self.plain_compare(a, b))
        output = []
        context = []
        for row in diff:
            mode = row[0:1] if row[0:1] in ['+', '-'] else ''
            line = row[2:]

            match = re.search(r'^(?P<depth>\s*).*', line)
            if match is not None:
                depth = len(match.groupdict().get('depth', ''))
            else:
                depth = 0

            ctx = {'line': line, 'depth': depth}
            if mode in ['+', '-']:
                context = list(filter(lambda x: x.get('depth') < depth, context))
                while len(context) > 0:
                    if text is True:
                        output.append(f'  {context.pop(0).get("line", "")}')
                    else:
                        output.append({'mode': mode, 'line': f'{context.pop(0).get("line", "")}'})
                if text is True:
                    output.append(f'{mode} {line}')
                else:
                    output.append({'mode': mode, 'line': f'{line}'})
            elif depth == 0:
                context = [ctx]
            elif len(context) > 0 and depth == context[-1].get('depth'):
                context.pop(-1)
                context.append(ctx)
            elif len(context) > 0 and depth > context[-1].get('depth'):
                context.append(ctx)
            elif len(context) > 0 and depth < context[-1].get('depth'):
                context = list(filter(lambda x: x.get('depth') < depth, context))
                context.append(ctx)

        return output


def get_backup_tables(instance):
    def get_backup_table(data):
        backups = []
        for row in data:
            commit = row.commit
            current = row
            previous = row.backup.changes.filter(file__type=row.file.type, commit__time__lt=commit.time).last()
            backup = {'pk': instance.pk, 'date': commit.time, 'current': current, 'previous': previous}
            backups.append(backup)

        table = BackupsTable(backups)
        return table

    backups = BackupCommitTreeChange.objects.filter(backup=instance).order_by('commit__time')

    tables = {}
    for file in ['running', 'startup']:
        try:
            tables.update({file: get_backup_table(backups.filter(file__type=file))})
        except KeyError:
            tables.update({file: get_backup_table([])})

    return tables


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


def enqueue_if_needed(backup, delay=None, job_id=None):
    if needs_enqueue(backup, job_id=job_id):
        enqueue(backup, delay=delay)


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

    if backup.device.primary_ip is None or backup.device.platform is None or \
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
    queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])

    if job_id is not None:
        queued.exclude(job_id=job_id)

    for backupjob in queued.all():
        job = queue.fetch_job(f'{backupjob.job_id}')
        if job and job.is_started and job.id in queue.started_job_registry.get_job_ids():
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


def is_queued(backup, job_id=None):
    queue = get_queue('netbox_config_backup.jobs')

    scheduled_jobs = queue.scheduled_job_registry.get_job_ids()
    started_jobs = queue.started_job_registry.get_job_ids()

    jobs = backup.jobs.all()
    queued = jobs.filter(status__in=[JobResultStatusChoices.STATUS_RUNNING, JobResultStatusChoices.STATUS_PENDING])

    if job_id is not None:
        queued.exclude(job_id=job_id)

    for backupjob in queued.all():
        job = queue.fetch_job(f'{backupjob.job_id}')
        if job and (job.is_scheduled or job.is_queued) and job.id in scheduled_jobs + started_jobs:
                return True
        elif job and (job.is_scheduled or job.is_queued) and job.id not in scheduled_jobs + started_jobs:
            job.cancel()
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
            logger.warning(f'Job in queue but not in a registry, cancelling')
        elif job and job.is_canceled:
            backupjob.status = JobResultStatusChoices.STATUS_FAILED
            backupjob.save()
    return False


def remove_orphaned(cls):
    queue = get_queue('netbox_config_backup.jobs')
    registry = ScheduledJobRegistry(queue=queue)

    for job_id in registry.get_job_ids():
        try:
            BackupJob.objects.get(job_id=job_id)
        except BackupJob.DoesNotExist:
            registry.remove(job_id)


def remove_queued(cls, backup):
    queue = get_queue('netbox_config_backup.jobs')
    registry = ScheduledJobRegistry(queue=queue)
    for job_id in registry.get_job_ids():
        job = queue.fetch_job(f'{job_id}')
        if backup.device is not None and job.description == f'backup-{backup.device.pk}':
            registry.remove(f'{job_id}')
