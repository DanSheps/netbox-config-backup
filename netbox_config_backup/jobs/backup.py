import dataclasses
import logging
import os
import uuid
import traceback
import multiprocessing
from datetime import timedelta, datetime

from django import db
from django.utils import timezone

from core.choices import JobStatusChoices, JobIntervalChoices
from netbox.api.exceptions import ServiceUnavailable
from netbox.jobs import JobRunner, system_job
from netbox.plugins import get_plugin_config
from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.models import Backup, BackupJob
from netbox_config_backup.utils.configs import check_config_save_status
from netbox_config_backup.utils.napalm import napalm_init
from netbox_config_backup.utils.rq import can_backup

__all__ = ('BackupRunner',)


logger = logging.getLogger("netbox_config_backup")

job_frequency = get_plugin_config('netbox_config_backup', 'job_frequency', 5)

if backup_frequency := get_plugin_config('netbox_config_backup', 'backup_frequency', None):
    backup_frequency = get_plugin_config('netbox_config_backup', 'frequency', 3600)


@dataclasses.dataclass()
class BackupResult:
    job: int
    pid: int
    status: str = 'running'
    config_save_status = None
    message: str = ''
    completed: datetime = None
    files: list = None


@system_job(interval=JobIntervalChoices.INTERVAL_MINUTELY * job_frequency)
class BackupRunner(JobRunner):
    processes = {}

    class Meta:
        name = 'Backup Job Runner'

    @classmethod
    def init_worker(cls):
        db.connections.close_all()

    @classmethod
    def fail_job(cls, jobs=None, status=JobStatusChoices.STATUS_FAILED, message=''):
        for job in jobs:
            job.status = status
            job.data.update({'error': {message}})
            job.full_clean()
        return BackupJob.objects.bulk_update(jobs, ['status', 'data'])

    @classmethod
    def clean_jobs(cls, backups=None):
        # Check for duplicate jobs
        if not backups:
            backups = Backup.objects.all()

        cutoff = timezone.now() - timedelta(minutes=job_frequency)

        counts = {}
        stuck = {}
        for backup in backups:
            count = {'stuck': 0, 'duplicated': 0, 'missed': 0}
            jobs = backup.jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
            running = jobs.filter(status__in=[JobStatusChoices.STATUS_RUNNING, JobStatusChoices.STATUS_PENDING])
            scheduled = jobs.filter(status__in=[JobStatusChoices.STATUS_SCHEDULED])
            if running.filter(scheduled__lte=cutoff).count() > 0:
                stuck = running.filter(scheduled__lte=cutoff).update(status=JobStatusChoices.STATUS_FAILED)
                count['stuck'] = stuck

            if running.count() > 1 and scheduled.count() >= 1:
                count['duplicated'] = jobs.exclude(pk=scheduled.last().pk).update(status=JobStatusChoices.STATUS_FAILED)
            elif running.count() > 1 and scheduled.count() == 0:
                filter = {
                    'started__lte': timezone.now() + timedelta(minutes=5),
                }
                count['duplicated'] = running.filter(**filter).update(status=JobStatusChoices.STATUS_FAILED)
            elif scheduled.count() > 1:
                count['duplicated'] = scheduled.exclude(pk=scheduled.last().pk).update(
                    status=JobStatusChoices.STATUS_FAILED
                )

            if count:
                counts.update({str(backup): count})
        return counts

    def schedule_missed_jobs(self, backups):
        if not backups:
            backups = Backup.objects.filter(device__isnull=False, status=StatusChoices.STATUS_ACTIVE)

        now = timezone.now()
        count = 0
        counts = {}
        for backup in backups:
            job = None
            if not can_backup(backup):
                jobs = backup.jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES)
                self.logger.debug(f'Cannot backup {backup}')
                failed = self.fail_job(jobs)
                if counts.get('failed', 0):
                    counts['failed'] += failed
                else:
                    counts['failed'] = failed
                continue

            if backup.jobs.filter(status__in=JobStatusChoices.ENQUEUED_STATE_CHOICES).count() == 0:
                if count > get_plugin_config('netbox_config_backup', 'workers', 10):
                    count = 0
                    now += timedelta(minutes=get_plugin_config('netbox_config_backup', 'offset', 5))
                job = BackupJob(
                    runner=None,
                    backup=backup,
                    status=JobStatusChoices.STATUS_SCHEDULED,
                    scheduled=now,
                    job_id=uuid.uuid4(),
                    data={},
                )
                job.full_clean()
                job.save()
                count += 1

            if job:
                counts.update({str(backup): count})
        return counts

    @classmethod
    def get_backup_jobs(cls, backups=None):

        jobs = BackupJob.objects.filter(backup__device__isnull=False, status=JobStatusChoices.STATUS_SCHEDULED)
        if backups:
            jobs = jobs.filter(backup__in=backups)
        jobs = jobs[0 : get_plugin_config('netbox_config_backup', 'workers', 10)]

        for job in jobs:
            job.status = JobStatusChoices.STATUS_PENDING
            job.full_clean()
            job.save()

        return jobs

    @classmethod
    def run_backup(cls, job_pk):
        result = BackupResult(pid=os.getpid(), job=job_pk)
        try:
            logger = logging.getLogger("netbox_config_backup")
            logger.info(f'Starting backup for job {job_pk}')
            try:
                job = BackupJob.objects.get(pk=job_pk)
            except Exception as e:
                logger.error(f'Unable to load job {job_pk}: {e}')
                logger.debug(f'\t{traceback.format_exc()}')
                raise e

            try:

                logger.debug(f'Checking backup status for {job}')
                if not can_backup(job.backup):
                    logger.info(f'Cannot backup {job.backup}')
                    result.status = JobStatusChoices.STATUS_FAILED
                    result.message = f'Cannot backup {job.backup}'
                    return result

                ip = job.backup.ip if job.backup.ip is not None else job.backup.device.primary_ip
                if ip:
                    logger.debug(f'Trying to connect to device {job.backup.device} with ip {ip} for {job}')
                    try:
                        d = napalm_init(job.backup.device, ip)
                    except (TimeoutError, ServiceUnavailable) as e:
                        logger.debug(f'Timeout Connecting to {job.backup.device} with ip {ip}')
                        result.status = (
                            JobStatusChoices.STATUS_FAILED
                            if result.status in [JobStatusChoices.ENQUEUED_STATE_CHOICES]
                            else result.status
                        )
                        result.message = f'Exception in {job_pk}: {e}'
                        return result

                    try:
                        logger.debug(f'Checking config save status for {job.backup}')
                        result.config_save_status = check_config_save_status(d)
                    except Exception as e:
                        logger.error(f'{job.backup}: had error setting backup status: {e}')

                    logger.debug(f'Getting config for {job.backup}')
                    configs = d.get_config()
                    logger.debug(f'Setting config for {job.backup}')
                    result.files = job.backup.write_config(configs)
                    logger.debug(f'Wrote config for {job.backup}')
                    logger.debug(f'Closing connection for {job.backup}')
                    result.completed = timezone.now()
                    result.status = JobStatusChoices.STATUS_COMPLETED
                    d.close()
            except Exception as e:
                logger.error(f'Exception in {job_pk}: {e}')
                logger.error(f'\t{traceback.format_exc()}')
                result.status = (
                    JobStatusChoices.STATUS_FAILED
                    if result.status in [JobStatusChoices.ENQUEUED_STATE_CHOICES]
                    else result.status
                )
                result.message = f'Exception in {job_pk}: {e}'
                return result
        except Exception as e:
            logger.error(f'Exception in {job_pk}: {e}')
            logger.error(f'\t{traceback.format_exc()}')
            result.status = (
                JobStatusChoices.STATUS_FAILED
                if result.status in [JobStatusChoices.ENQUEUED_STATE_CHOICES]
                else result.status
            )
            result.message = f'Exception in {job_pk}: {e}'
        return result

    def schedule_job(self, jobs):
        frequency = get_plugin_config('netbox_config_backup', 'frequency', 3600)
        new_jobs = []
        counts = {
            'scheduled': 0,
            'failed': 0,
        }
        for job in jobs:
            job.refresh_from_db()
            self.logger.debug(f'Scheduling next backup for {job.backup}')
            if job.status in JobStatusChoices.TERMINAL_STATE_CHOICES:
                scheduled = job.completed + timedelta(seconds=frequency)
                self.logger.debug(f'Elligible for: {scheduled}')
                new_job = BackupJob(
                    runner=None,
                    backup=job.backup,
                    status=JobStatusChoices.STATUS_SCHEDULED,
                    scheduled=scheduled,
                    job_id=uuid.uuid4(),
                    data={},
                )
                new_job.full_clean()
                new_job.save()
                new_jobs.append(new_job)
                counts['scheduled'] += 1
            else:
                self.logger.debug(f'Not eligible for: {job.backup} due to state: {job.status}')
                counts['failed'] += 1

        return jobs

    def run(self, backup: Backup = None, *args, **kwargs):
        try:
            started = timezone.now()
            if backup is not None:
                backups = [
                    backup,
                ]
            else:
                backups = []

            job_start = timezone.now()
            # Clean Job
            count = self.clean_jobs(backups=backups)
            job_end = timezone.now()
            self.logger.info(
                f'Cleaned {count} jobs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()
            # Schedule missed jobs
            count = self.schedule_missed_jobs(backups=backups)
            job_end = timezone.now()
            self.logger.info(
                f'Scheduled {count} missed jobs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()
            # Get backup jobs
            jobs = self.get_backup_jobs(backups=backups)
            job_end = timezone.now()
            self.logger.info(
                f'Got {len(jobs)} jobs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()
            # Change jobs to run status before we begin
            for job in jobs:
                job.status = JobStatusChoices.STATUS_RUNNING
                job.started = timezone.now()
                job.full_clean()
                job.save()

            # Close DB Connections to prevent file descriptor leakage between instances
            job_end = timezone.now()
            self.logger.info(
                f'Updated {len(jobs)} jobs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()
            db.connections.close_all()
            # Startup multiple workers to grab queued configs
            with multiprocessing.Pool(
                processes=get_plugin_config('netbox_config_backup', 'workers', 10), initializer=self.init_worker
            ) as pool:
                # Report the results
                results = pool.map(self.run_backup, [job.pk for job in jobs])
            job_end = timezone.now()
            self.logger.info(
                f'Obtained {len(results)} configs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()
            # Perform the commit
            commit = Backup.commit(jobs)
            job_end = timezone.now()
            self.logger.info(
                f'Commit configs ({commit if commit else '' }). Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            if commit:
                job_start = timezone.now()
                # Update the DB
                for job in jobs:
                    job.backup.update_commit_tree(commit=commit)
                job_end = timezone.now()
                self.logger.info(
                    f'Updated Commit Tree. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                    f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
                )

            job_start = timezone.now()

            # Update the job in DB
            for result in results:
                job = BackupJob.objects.get(pk=result.job)
                logger.info(f'Updating job {job} with result: {result.status}')
                job.status = result.status
                job.completed = result.completed
                job.data = {'files': result.files} if result.files else {}
                if result.message:
                    job.data.update({'message': result.message})
                job.full_clean()
                job.save()
                job.backup.config_status = result.config_save_status.get('status', False)
                job.backup.full_clean()
                job.backup.save()
            job_end = timezone.now()
            self.logger.info(
                f'Updated job results. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

            job_start = timezone.now()

            self.schedule_job(jobs)
            job_end = timezone.now()
            self.logger.info(
                f'Scheduled new jobs. Time taken: {(job_end - job_start).total_seconds()} seconds. '
                f'Total elapsed: {(job_end - started).total_seconds()} seconds.'
            )

        except Exception as e:
            traceback.print_exc()
            raise e
