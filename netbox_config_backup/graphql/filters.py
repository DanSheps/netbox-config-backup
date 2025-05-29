from typing import Annotated

import strawberry
import strawberry_django

from netbox_config_backup import filtersets, models

from netbox.graphql.filter_mixins import BaseObjectTypeFilterMixin

__all__ = (
    'BackupFilter',
)


@strawberry_django.filter(models.Backup, lookups=True)
class BackupFilter(BaseObjectTypeFilterMixin):
    device: Annotated['DeviceFilter', strawberry.lazy('dcim.graphql.filters')] | None = strawberry_django.filter_field()
    device_id: strawberry.ID | None = strawberry_django.filter_field()
