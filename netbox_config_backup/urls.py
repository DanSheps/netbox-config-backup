from django.urls import path

from netbox.views.generic import ObjectChangeLogView
from . import views
from .models import Backup

urlpatterns = [
    path('jobs/', views.BackupJobListView.as_view(), name='backupjob_list'),
    path('unassigned/', views.UnassignedBackupListView.as_view(), name='unassignedbackup_list'),
    path('devices/', views.BackupListView.as_view(), name='backup_list'),
    path('devices/add/', views.BackupEditView.as_view(), name='backup_add'),
    path('devices/<int:pk>/', views.BackupView.as_view(), name='backup'),
    path('devices/<int:pk>/changelog', ObjectChangeLogView.as_view(), name="backup_changelog", kwargs={'model': Backup}),
    path('devices/<int:pk>/edit/', views.BackupEditView.as_view(), name='backup_edit'),
    path('devices/<int:pk>/delete/', views.BackupDeleteView.as_view(), name='backup_delete'),
    path('devices/<int:pk>/backups/', views.BackupBackupsView.as_view(), name='backup_backups'),
    path('devices/<int:backup>/config/', views.ConfigView.as_view(), name='backup_config'),
    path('devices/<int:backup>/config/<int:current>/', views.ConfigView.as_view(), name='backup_config'),
    path('devices/<int:backup>/diff/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:backup>/diff/<int:current>/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:backup>/compliance/', views.ComplianceView.as_view(), name='backup_compliance'),
    path('devices/<int:backup>/compliance/<int:current>/', views.ComplianceView.as_view(), name='backup_compliance'),
    path('devices/edit/', views.BackupBulkEditView.as_view(), name='backup_bulk_edit'),
    path('devices/delete/', views.BackupBulkDeleteView.as_view(), name='backup_bulk_delete'),
    path('devices/<int:backup>/diff/<int:current>/<int:previous>/', views.DiffView.as_view(), name='backup_diff'),
]
