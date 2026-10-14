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

#
# TODO: jobs/testmulti.py defines NCBTestJob (a 2-minute sleep loop) with the misleading name 'Backup
# Housekeeping', __all__ = 'BackupHousekeeping', and unused imports. It looks like a leftover
# debugging file that later readers will confuse with the real housekeeping job.
# https://app.qodo.ai/findings/99acd54e-ff82-4643-a2ce-d3563e3ff5a4
#
class NCBTestJob(JobRunner):

    class Meta:
        name = 'Backup Housekeeping'

    def run(self, *args, **kwargs):
        # Will be removed in a while
        start = timezone.now()
        end = timezone.now() + timedelta(minutes=2)

        while timezone.now() < end:
            time.sleep(5)