from django.urls import path
from . import views

urlpatterns = [
    path('devices/', views.BackupListView.as_view(), name='backup_list'),
    path('devices/add/', views.BackupEditView.as_view(), name='backup_add'),
    path('devices/<int:pk>/', views.BackupView.as_view(), name='backup'),
    path('devices/<int:pk>/edit/', views.BackupEditView.as_view(), name='backup_edit'),
    path('devices/<int:pk>/delete/', views.BackupDeleteView.as_view(), name='backup_delete'),
    path('devices/<int:pk>/config/<str:index>/<str:file>/', views.ConfigView.as_view(), name='backup_config'),
    path('devices/<int:pk>/diff/<str:index>/<str:file>/', views.DiffView.as_view(), name='backup_diff'),
    path('devices/<int:pk>/diff/<str:index>/<str:file>/<str:previous>/', views.DiffView.as_view(), name='backup_diff'),
]