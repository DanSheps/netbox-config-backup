from django.urls import path, include

from utilities.urls import get_model_urls
from . import views

urlpatterns = [
    path('backups/', include(get_model_urls('netbox_config_backup', 'backup', detail=False))),
    path('backups/<int:pk>/', include(get_model_urls('netbox_config_backup', 'backup'))),
    path('devices/', include(get_model_urls('netbox_config_backup', 'backup', detail=False))),
    path('devices/<int:pk>/', include(get_model_urls('netbox_config_backup', 'backup'))),
    path('devices/<int:pk>/config/', views.DiffView.as_view(), name='backup_config'),
    path('devices/<int:pk>/diff/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:pk>/diff/<int:current>/', views.DiffView.as_view(), name='backup_diff'),
    path('jobs/', include(get_model_urls('netbox_config_backup', 'backupjob', detail=False))),
    path('jobs/<int:pk>/', include(get_model_urls('netbox_config_backup', 'backupjob'))),
]
