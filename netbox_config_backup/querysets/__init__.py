from django.db import models
from django.db.models import Count

from extras.choices import JobResultStatusChoices
from utilities.querysets import RestrictedQuerySet



class BackupQuerySet(RestrictedQuerySet):
    def default_annotate(self):
        from netbox_config_backup.models import BackupJob, BackupCommitTreeChange

        return self.prefetch_related('jobs', 'changes', 'changes__commit')
        #.annotate(
        #last_backup=models.Subquery(
        #    BackupJob.objects.filter(backup=models.OuterRef('id'), status=JobResultStatusChoices.STATUS_COMPLETED).order_by('-completed').values('completed')[:1]
        #),
        #next_attempt=models.Subquery(
        #    BackupJob.objects.filter(backup=models.OuterRef('id'), status__in=['pending', 'running']).order_by('-scheduled').values('scheduled')[:1]
        #),
        #last_change=models.Subquery(
        #    BackupCommitTreeChange.objects.filter(backup=models.OuterRef('id')).order_by('-id').values('commit__time')[:1]
        #)
    #)