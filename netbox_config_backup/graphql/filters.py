from typing import Annotated, TYPE_CHECKING

# Base Imports
import strawberry
import strawberry_django

# NetBox Imports
from netbox.graphql.filter_mixins import BaseObjectTypeFilterMixin

# Plugin Imports
from netbox_config_backup import models

if TYPE_CHECKING:
    from dcim.graphql.filters import DeviceFilter


__all__ = ('BackupFilter',)


@strawberry_django.filter(models.Backup, lookups=True)
class BackupFilter(BaseObjectTypeFilterMixin):
    device: (
        Annotated['DeviceFilter', strawberry.lazy('dcim.graphql.filters')]
        | None  # noqa: F821
    ) = strawberry_django.filter_field()  # noqa: F821
    device_id: strawberry.ID | None = strawberry_django.filter_field()
