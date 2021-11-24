import django_filters
from django.db.models import Q
from netbox_plugin_extensions.filtersets import PluginPrimaryModelFilterSet

from dcim.models import Device
from netbox_config_backup import models


class BackupFilterSet(PluginPrimaryModelFilterSet):
    q = django_filters.CharFilter(
        method='search',
        label='Search',
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name',
        queryset=Device.objects.all(),
        to_field_name='name',
        label='Device (name)',
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        label='Device (ID)',
    )

    class Meta:
        model = models.Backup
        fields = ['id', 'name']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value) |
            Q(device__name__icontains=value)
        )
        return queryset.filter(qs_filter)
