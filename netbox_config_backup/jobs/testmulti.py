import logging
import time
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

class NCBTestJob(JobRunner):

    class Meta:
        name = 'Backup Housekeeping'

    def run(self, *args, **kwargs):
        # Will be removed in a while
        start = timezone.now()
        end = timezone.now() + timedelta(minutes=2)

        while timezone.now() < end:
            time.sleep(5)