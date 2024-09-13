import strawberry_django
from netbox_config_backup import filtersets, models

from netbox.graphql.filter_mixins import autotype_decorator, BaseFilterMixin

__all__ = (
    'BackupFilter',
)


@strawberry_django.filter(models.Backup, lookups=True)
@autotype_decorator(filtersets.BackupFilterSet)
class BackupFilter(BaseFilterMixin):
    pass
