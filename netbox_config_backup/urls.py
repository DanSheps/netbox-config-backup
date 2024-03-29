from django.urls import path
from . import views

urlpatterns = [
    path('unassigned/', views.UnassignedBackupListView.as_view(), name='unassignedbackup_list'),
    path('devices/', views.BackupListView.as_view(), name='backup_list'),
    path('devices/add/', views.BackupEditView.as_view(), name='backup_add'),
    path('devices/<int:pk>/', views.BackupView.as_view(), name='backup'),
    path('devices/<int:pk>/edit/', views.BackupEditView.as_view(), name='backup_edit'),
    path('devices/<int:pk>/delete/', views.BackupDeleteView.as_view(), name='backup_delete'),
    path('devices/<int:pk>/backups/', views.BackupBackupsView.as_view(), name='backup_backups'),
    path('devices/<int:backup>/config/', views.ConfigView.as_view(), name='backup_config'),
    path('devices/<int:backup>/config/<int:current>/', views.ConfigView.as_view(), name='backup_config'),
    path('devices/<int:backup>/diff/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:backup>/diff/<int:current>/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:backup>/diff/<int:current>/<int:previous>/', views.DiffView.as_view(), name='backup_diff'),
]
