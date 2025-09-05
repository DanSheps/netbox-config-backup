import django_filters
import netaddr
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from netaddr import AddrFormatError

from netbox.filtersets import BaseFilterSet
from dcim.models import Device
from netbox_config_backup import models
from netbox_config_backup.choices import FileTypeChoices


class BackupJobFilterSet(BaseFilterSet):
    q = django_filters.CharFilter(
        method='search',
        label=_('Search'),
    )

    class Meta:
        model = models.BackupJob
        fields = ['id', 'status']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(backup__name__icontains=value)
            | Q(backup__ip__address__icontains=value)
            | Q(backup__device__name__icontains=value)
        )

        return queryset.filter(qs_filter)


class BackupFilterSet(BaseFilterSet):
    q = django_filters.CharFilter(
        method='search',
        label=_('Search'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name',
        queryset=Device.objects.all(),
        to_field_name='name',
        label=_('Device (name)'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        label=_('Device (ID)'),
    )
    config_status = django_filters.BooleanFilter(
        field_name='config_status',
        label=_('Config Saved'),
    )
    ip = django_filters.CharFilter(
        method='filter_address',
        label=_('Address'),
    )

    class Meta:
        model = models.Backup
        fields = ['id', 'name', 'ip']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(device__name__icontains=value)
            | Q(device__primary_ip4__address__contains=value.strip())
            | Q(device__primary_ip6__address__contains=value.strip())
            | Q(ip__address__contains=value.strip())
        )

        try:
            prefix = str(netaddr.IPNetwork(value.strip()).cidr)
            qs_filter |= Q(device__primary_ip4__address__net_host_contained=prefix)
            qs_filter |= Q(device__primary_ip6__address__net_host_contained=prefix)
            qs_filter |= Q(ip__address__net_host_contained=prefix)

        except (AddrFormatError, ValueError):
            pass

        return queryset.filter(qs_filter)

    def filter_address(self, queryset, name, value):
        try:
            if type(value) is list:
                query = Q()
                for val in value:
                    query |= Q(ip__address__net_host_contained=val)
                return queryset.filter(query)
            else:
                return queryset.filter(ip__address__net_host_contained=value)
        except ValidationError:
            return queryset.none()


class BackupsFilterSet(BaseFilterSet):
    q = django_filters.CharFilter(
        method='search',
        label=_('Search'),
    )
    type = django_filters.MultipleChoiceFilter(
        field_name='file__type', choices=FileTypeChoices, null_value=None
    )

    class Meta:
        model = models.BackupCommitTreeChange
        fields = ['id', 'file']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(file__type=value) | Q(file__type__startswith=value)
        return queryset.filter(qs_filter)
