from netbox.api.routers import NetBoxRouter
from .views import *


router = NetBoxRouter()
router.register('backup', BackupViewSet)
urlpatterns = router.urls
