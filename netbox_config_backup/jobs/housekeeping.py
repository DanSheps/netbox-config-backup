import logging
from datetime import timedelta

from django.utils import timezone
from rq.job import JobStatus

from core.choices import JobIntervalChoices, JobStatusChoices
from core.models import Job
from netbox import settings
from netbox.jobs import JobRunner, system_job

from netbox_config_backup.jobs import BackupRunner

__all__ = 'BackupHousekeeping'

logger = logging.getLogger("netbox_config_backup")

job_frequency = settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('frequency', 3600)


@system_job(interval=JobIntervalChoices.INTERVAL_HOURLY * 2)
class BackupHousekeeping(JobRunner):

    class Meta:
        name = 'Backup Housekeeping'

    def run(self, *args, **kwargs):
        # Will be removed in a while
        names = ['The Backup Job Runner', BackupRunner.name]
        jobs = Job.objects.filter(name__in=names, status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
        if jobs.count() > 0:
            for job in jobs:
                if job.scheduled < timezone.now() - timedelta(minutes=30):
                    logger.info(f'Backup Job Runner {job} ({job.pk} is stale')
                    job.status = JobStatus.FAILED
                    job.clean()
                    job.save()
                    job = BackupRunner.enqueue(scheduled_at=timezone.now() + timedelta(minutes=5))
                    logger.info(f'\tNew Backup Job Runner enqueued as {job} ({job.pk})')
        else:
            logger.info('No stale jobs')
