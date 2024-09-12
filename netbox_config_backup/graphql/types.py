from typing import Annotated

import strawberry
import strawberry_django

from netbox.graphql.types import NetBoxObjectType
from .filters import *

from netbox_config_backup import models

__all__ = (
    'BackupType',
)


@strawberry_django.type(
    models.Backup,
    fields='__all__',
    filters=BackupFilter
)
class BackupType(NetBoxObjectType):

    name: str
    device: Annotated["DeviceType", strawberry.lazy('dcim.graphql.types')] | None
    ip: Annotated["IPAddressType", strawberry.lazy('ipam.graphql.types')] | None
