from typing import List

import strawberry
import strawberry_django

from .types import *


@strawberry.type(name="Query")
class BackupQuery:
    backup: BackupType = strawberry_django.field()
    backup_list: List[BackupType] = strawberry_django.field()


schema = [
    BackupQuery,
]
