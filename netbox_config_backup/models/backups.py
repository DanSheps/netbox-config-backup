import logging
import uuid as uuid

from django.db import models
from django.urls import reverse

from django_rq import get_queue
from django_rq import get_queue
from rq.registry import ScheduledJobRegistry

from dcim.models import Device
from netbox.models import BigIDModel
from netbox_config_backup.choices import FileTypeChoices, CommitTreeChangeTypeChoices
from netbox_config_backup.helpers import get_repository_dir
from utilities.querysets import RestrictedQuerySet

logger = logging.getLogger(f"netbox_config_backup")


class Backup(BigIDModel):
    name = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        to=Device,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    objects = RestrictedQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    @property
    def last_backup(self):
        commit = self.commits.last()
        if commit is not None:
            return commit.time
        return None

    @property
    def next_attempt(self):
        job = self.jobs.filter(status__in=['pending', 'running']).orderby('time').last()
        if job is not None:
            return job.scheduled
        return None

    def get_absolute_url(self):
        return reverse('plugins:netbox_config_backup:backup', args=[self.pk])

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        queue = get_queue('netbox_config_backup.jobs')
        registry = ScheduledJobRegistry(queue=queue)
        for job_id in registry.get_job_ids():
            job = queue.fetch_job(job_id)
            if job.description == f'backup-{self.device.pk}':
                registry.remove(job_id)

        super().delete(*args, **kwargs)

    def get_config(self, index='HEAD'):
        from netbox_config_backup.git import repository
        running = repository.read(f'{self.uuid}.running')
        startup = repository.read(f'{self.uuid}.startup')

        return {'running': running, 'startup': startup}

    def set_config(self, configs, files=('running', 'startup')):
        from netbox_config_backup.git import repository

        for file in files:
            running = repository.write(f'{self.uuid}.{file}', configs.get(file))

        commit = repository.commit(f'Backup of {self.device.name}')

        log = repository.log(index=commit, depth=1)[0]

        bc = BackupCommit.objects.filter(backup=self, sha=commit)
        if bc.count() > 0:
            raise Exception('Commit already exists for this backup and sha value')
        else:
            bc = BackupCommit(backup=self, sha=commit, time=log.get('time'))
            logger.info(f'{commit}:{bc.time}')
            bc.save()

        for change in log.get('changes', []):
            change_data = {}
            for key in ['old', 'new']:
                sha = change.get(key, {}).get('sha', None)
                file = change.get(key, {}).get('path', None)
                if sha is not None and file is not None:
                    object = BackupObject.objects.filter(sha=sha, file=file)
                    if object.count() > 1:
                        raise Exception('Commit log integrity error')
                    elif object.count() == 1:
                        object = object.first()
                    else:
                        object = BackupObject(sha=sha, file=file)
                        object.save()
                    change_data[key] = object

            bctc = BackupCommitTreeChange.objects.filter(
                commit=bc,
                type=change.get('type', None),
                old=change_data.get('old', None),
                new=change_data.get('new', None)
            )
            if bctc.count() > 0:
                bctc = bctc.first()
            elif bctc.count() == 0:
                bctc = BackupCommitTreeChange(
                    commit=bc,
                    type=change.get('type', None),
                    old=change_data.get('old', None),
                    new=change_data.get('new', None)
                )
                bctc.save()

        return commit

    @classmethod
    def rebuild_commit_database(cls):
        from netbox_config_backup.git import repository

        def save_change(bc, change):
            change_data = {}
            for key in ['old', 'new']:
                sha = change.get(key, {}).get('sha', None)
                file = change.get(key, {}).get('path', None)
                if sha is not None and file is not None:
                    try:
                        object = BackupObject.objects.get(sha=sha, file=file)
                    except BackupObject.DoesNotExist:
                        object = BackupObject(sha=sha, file=file)
                        object.save()
                    change_data[key] = object

            try:
                bctc = BackupCommitTreeChange.objects.get(
                    commit=bc,
                    type=change.get('type', None),
                    old=change_data.get('old', None),
                    new=change_data.get('new', None)
                )
            except BackupCommitTreeChange.DoesNotExist:
                bctc = BackupCommitTreeChange(
                    commit=bc,
                    type=change.get('type', None),
                    old=change_data.get('old', None),
                    new=change_data.get('new', None)
                )
                bctc.save()

        backups = Backup.objects.all()
        for backup in backups:
            paths = []
            for file in ['running', 'startup']:
                paths.append(f'{backup.uuid}.{file}')
            logs = reversed(repository.log(paths=paths))
            for entry in logs:
                try:
                    bc = BackupCommit.objects.get(sha=entry.get('sha', None))
                    if bc.time is None or (entry.get('time') is not None and bc.time != entry.get('time')):
                        bc.time = entry.get('time')
                        bc.save()
                except BackupCommit.DoesNotExist:
                    bc = BackupCommit(backup=backup, sha=entry.get('sha', None), time=entry.get('time'))
                    bc.save()
                for change in entry.get('changes', []):
                    save_change(bc, change)


    @classmethod
    def get_repository_dir(cls):
        return get_repository_dir()


class BackupCommit(BigIDModel):
    backup = models.ForeignKey(to=Backup, on_delete=models.SET_NULL, null=True, blank=False, related_name='commits')
    sha = models.CharField(max_length=64)
    time = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name='backup_and_sha_not_null',
                check=(models.Q(backup__isnull=False, sha__isnull=False))
            )
        ]

    def __str__(self):
        return self.sha


class BackupObject(BigIDModel):
    sha = models.CharField(max_length=64)
    file = models.CharField(max_length=255)

    class Meta:
        unique_together = ['sha', 'file']

    def __str__(self):
        return f'{self.sha}({self.file})'


class BackupCommitTreeChange(BigIDModel):
    commit = models.ForeignKey(to=BackupCommit, on_delete=models.PROTECT, related_name='changes')
    type = models.CharField(max_length=10)
    old = models.ForeignKey(to=BackupObject, on_delete=models.PROTECT, related_name='previous', null=True)
    new = models.ForeignKey(to=BackupObject, on_delete=models.PROTECT, related_name='new', null=True)

    def __str__(self):
        return f'{self.commit.sha}-{self.type}'
