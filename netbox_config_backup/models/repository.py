from django.db import models
from django.urls import reverse

from netbox_config_backup.choices import FileTypeChoices
from netbox_config_backup.models import Backup
from netbox_config_backup.models.abstract import BigIDModel


class BackupCommit(BigIDModel):
    sha = models.CharField(max_length=64)
    time = models.DateTimeField()

    class Meta:
        ordering = ('pk',)

    def __str__(self):
        return self.sha


class BackupObject(BigIDModel):
    sha = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ('pk',)

    def __str__(self):
        return f'{self.sha}'


class BackupFile(BigIDModel):
    backup = models.ForeignKey(
        to=Backup,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='files',
    )
    type = models.CharField(max_length=10, choices=FileTypeChoices, null=False, blank=False)

    last_change = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('pk',)
        unique_together = ['backup', 'type']

    def __str__(self):
        return f'{self.name}.{self.type}'

    @property
    def name(self):
        return f'{self.backup.uuid}'

    @property
    def path(self):
        return f'{self.name}.{self.type}'


class BackupCommitTreeChange(BigIDModel):
    backup = models.ForeignKey(
        to=Backup,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='changes',
    )
    file = models.ForeignKey(
        to=BackupFile,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='changes',
    )

    commit = models.ForeignKey(to=BackupCommit, on_delete=models.PROTECT, related_name='changes')
    type = models.CharField(max_length=10)
    old = models.ForeignKey(to=BackupObject, on_delete=models.PROTECT, related_name='previous', null=True)
    new = models.ForeignKey(to=BackupObject, on_delete=models.PROTECT, related_name='changes', null=True)

    class Meta:
        ordering = ('pk',)

    def __str__(self):
        return f'{self.commit.sha}-{self.type}'

    def filename(self):
        return f'{self.backup.uuid}.{self.type}'

    def get_absolute_url(self):
        return reverse(
            'plugins:netbox_config_backup:backup_config',
            kwargs={'pk': self.backup.pk, 'current': self.pk},
        )

    @property
    def previous(self):
        return self.backup.changes.filter(file__type=self.file.type, commit__time__lt=self.commit.time).last()
