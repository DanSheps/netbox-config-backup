import logging
import datetime
import os
import uuid as uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from dcim.models import Device
from netbox.models import PrimaryModel

from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.helpers import get_repository_dir
from ..git import repository

from ..querysets import BackupQuerySet
from ..utils import Differ


logger = logging.getLogger("netbox_config_backup")


class Backup(PrimaryModel):
    name = models.CharField(max_length=255, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=50, choices=StatusChoices, default=StatusChoices.STATUS_ACTIVE
    )
    device = models.ForeignKey(
        to=Device,
        on_delete=models.SET_NULL,
        related_name='backups',
        blank=True,
        null=True,
    )
    ip = models.ForeignKey(
        to='ipam.IPAddress', on_delete=models.SET_NULL, blank=True, null=True
    )
    config_status = models.BooleanField(blank=True, null=True)

    objects = BackupQuerySet.as_manager()

    class Meta:
        ordering = ('name',)

    def get_absolute_url(self):
        return reverse('plugins:netbox_config_backup:backup', args=[self.pk])

    def __str__(self):
        return self.name

    def get_config(self, index='HEAD'):

        running = repository.read(f'{self.uuid}.running')
        startup = repository.read(f'{self.uuid}.startup')

        return {
            'running': running if running is not None else '',
            'startup': startup if startup is not None else '',
        }

    def write_config(self, configs, files=('running', 'startup')):
        stored_configs = self.get_config()
        changes = []
        for file in files:
            stored = stored_configs.get(file) if stored_configs.get(file) is not None else ''
            current = configs.get(file) if configs.get(file) is not None else ''
            if Differ(stored, current).is_diff():
                path = f'{repository.location}{os.path.sep}{self.uuid}.{file}'
                changes.append({'name': f'{self.name}', 'uuid': f'{self.uuid}', f'path': f'{path}'})
                with open(path, 'w') as f:
                    f.write(current)
                    f.close()

        return changes

    @classmethod
    def commit(self, jobs):
        backups = [str(job.backup) for job in jobs]
        commit = repository.commit(
            f'Backup commit for backup jobs: {",".join(backups)} on {timezone.now()}',
        )
        return commit

    @classmethod
    def rebuild_bctc_full(cls):
        for backup in cls.objects.all():
            backup.rebuild_bctc()

    def rebuild_bctc(self):
        from netbox_config_backup.models.repository import BackupCommitTreeChange
        commits = self.update_commit_tree(depth=None)
        # print(f'Validated {len(commits)}')
        pks = [commit.pk for commit in commits]
        orphan_commits = BackupCommitTreeChange.objects.filter(pk=self.pk).exclude(pk__in=pks)
        if orphan_commits.count() > 0:
            deleted = orphan_commits.delete()
            # print(f'Deleted {deleted[0]} orphan commits')

    def update_commit_tree(self, commit = None, depth = 1):
        from netbox_config_backup.models.repository import (
            BackupCommit,
            BackupObject,
            BackupFile,
            BackupCommitTreeChange,
        )

        backupfiles = BackupFile.objects.filter(backup=self)

        if not commit:
            logs = repository.log(index='HEAD', depth=depth, uuid=self.uuid)
        else:
            logs = repository.log(index=commit, depth=1, uuid=self.uuid)

        commits = []
        for log in reversed(logs):
            commit = log.get('sha')
            if len(log.get('parents', [])) > 1:
                raise Exception('Not programmed to handle more then 1 parent')
            parent = log.get('parents', []).pop() if log.get('parents', []) else None
            time = log.get('time')
            try:
                bc = BackupCommit.objects.get(sha=commit)
            except BackupCommit.DoesNotExist:
                bc = BackupCommit(sha=commit, time=time)
                bc.full_clean()
                bc.save()

            for change in log.get('changes', []):
                change_data = {}
                for key in ['old', 'new']:
                    sha = change.get(key, {}).get('sha', None)
                    file = change.get(key, {}).get('path', None)
                    uuid, type = file.split('.') if file is not None else (None, None)
                    if str(uuid) != str(self.uuid):
                        # Not the change associated with this commit so exit the inner loop
                        continue
                    try:
                        object = BackupObject.objects.get(sha=sha)
                    except BackupObject.DoesNotExist:
                        object = BackupObject.objects.create(sha=sha)

                    if backupfiles.filter(type=type).count() == 0:
                        backupfile = BackupFile(backup=self, type=type)
                        backupfile.full_clean()
                        backupfile.save()

                    change_data[key] = object
                if str(uuid) != str(self.uuid):
                    continue
                try:
                    bctc = BackupCommitTreeChange.objects.get(
                        backup=self,
                        file=backupfiles.get(type=type),
                        commit=bc,
                        type=change.get('type', None),
                        old=change_data.get('old', None),
                        new=change_data.get('new', None),
                    )
                except BackupCommitTreeChange.DoesNotExist:
                    bctc = BackupCommitTreeChange(
                        backup=self,
                        file=backupfiles.get(type=type),
                        commit=bc,
                        type=change.get('type', None),
                        old=change_data.get('old', None),
                        new=change_data.get('new', None),
                    )
                    bctc.save()
                commits.append(bctc)

        return commits

    @classmethod
    def get_repository_dir(cls):
        return get_repository_dir()
