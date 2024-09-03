import logging
import datetime
import uuid as uuid

from django.db import models
from django.db.models import Q
from django.urls import reverse

from django_rq import get_queue

from dcim.models import Device
from core.choices import JobStatusChoices
from netbox.models import NetBoxModel

from netbox_config_backup.choices import StatusChoices
from netbox_config_backup.helpers import get_repository_dir

from netbox_config_backup.utils.rq import remove_queued
from ..querysets import BackupQuerySet
from ..utils import Differ

logger = logging.getLogger(f"netbox_config_backup")


class Backup(NetBoxModel):
    name = models.CharField(max_length=255, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=50,
        choices=StatusChoices,
        default=StatusChoices.STATUS_ACTIVE
    )
    device = models.ForeignKey(
        to=Device,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    ip = models.ForeignKey(
        to='ipam.IPAddress',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    objects = BackupQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def get_absolute_url(self):
        return reverse('plugins:netbox_config_backup:backup', args=[self.pk])

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        queue = get_queue('netbox_config_backup.jobs')
        remove_queued(self)

        super().delete(*args, **kwargs)

    def enqueue_if_needed(self):
        from netbox_config_backup.utils.rq import enqueue_if_needed
        return enqueue_if_needed(self)

    def requeue(self):
        self.jobs.filter(
            ~Q(status=JobStatusChoices.STATUS_COMPLETED) &
            ~Q(status=JobStatusChoices.STATUS_FAILED) &
            ~Q(status=JobStatusChoices.STATUS_ERRORED)
        ).update(
            status=JobStatusChoices.STATUS_FAILED
        )
        remove_queued(self)
        self.enqueue_if_needed()

    def get_config(self, index='HEAD'):
        from netbox_config_backup.git import repository
        running = repository.read(f'{self.uuid}.running')
        startup = repository.read(f'{self.uuid}.startup')

        return {'running': running if running is not None else '', 'startup': startup if startup is not None else ''}

    def set_config(self, configs, files=('running', 'startup'), pk=None):
        from netbox_config_backup.models.repository import (BackupCommit, BackupObject, BackupFile,
                                                            BackupCommitTreeChange)
        from netbox_config_backup.git import repository
        LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

        stored_configs = self.get_config()
        changes = False
        for file in files:
            #logger.debug(f'[{pk}] Getting existing config for {file}')
            stored = stored_configs.get(file) if stored_configs.get(file) is not None else ''
            #logger.debug(f'[{pk}] Getting new config')
            current = configs.get(file) if configs.get(file) is not None else ''
            #logger.debug(f'[{pk}] Starting diff for {file}')
            if Differ(stored, current).is_diff():
                changes = True
                output = repository.write(f'{self.uuid}.{file}', current)
            #logger.debug(f'[{pk}] Finished diff for {file}')
        if not changes:
            return None

        #logger.debug(f'[{pk}] Commiting files')
        commit = repository.commit(f'Backup of {self.device.name} for backup {self.name}')

        #logger.debug(f'[{pk}] Getting repository log')
        log = repository.log(index=commit, depth=1)[0]

        #logger.debug(f'[{pk}] Saving commit to DB')
        bc = BackupCommit.objects.filter(sha=commit)
        time = log.get('time', datetime.datetime.now()).replace(tzinfo=LOCAL_TIMEZONE)
        if bc.count() > 0:
            #logger.debug(f'[{pk}] Error committing')
            raise Exception('Commit already exists for this backup and sha value')
        else:
            #logger.debug(f'[{pk}] Saving commit')
            bc = BackupCommit(sha=commit, time=time)
            logger.info(f'{self}: {commit}:{bc.time}')
            bc.save()

        for change in log.get('changes', []):
            #logger.debug(f'[{pk}] Adding backup tree changes')
            backupfile = None
            change_data = {}
            for key in ['old', 'new']:
                sha = change.get(key, {}).get('sha', None)
                file = change.get(key, {}).get('path', None)
                if sha is not None and file is not None:
                    uuid, type = file.split('.')
                    try:
                        object = BackupObject.objects.get(sha=sha)
                    except BackupObject.DoesNotExist:
                        object = BackupObject.objects.create(sha=sha)
                    try:
                        backupfile = BackupFile.objects.get(backup=self, type=type)
                    except BackupFile.DoesNotExist:
                        backupfile = BackupFile.objects.create(backup=self, type=type)
                    change_data[key] = object

            bctc = BackupCommitTreeChange.objects.filter(
                backup=self,
                file=backupfile,
                commit=bc,
                type=change.get('type', None),
                old=change_data.get('old', None),
                new=change_data.get('new', None)
            )
            if bctc.count() > 0:
                bctc = bctc.first()
            elif bctc.count() == 0:
                bctc = BackupCommitTreeChange(
                    backup=self,
                    file=backupfile,
                    commit=bc,
                    type=change.get('type', None),
                    old=change_data.get('old', None),
                    new=change_data.get('new', None)
                )
                bctc.save()
                #logger.debug(f'[{pk}] Tree saved')
        #logger.debug(f'[{pk}] Get config saved')
        return commit

    @classmethod
    def get_repository_dir(cls):
        return get_repository_dir()