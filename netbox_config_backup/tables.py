import django_tables2 as tables
from django_tables2.utils import Accessor

from netbox_config_backup.models import Backup
from netbox.tables import columns, BaseTable


class ActionButtonsColumn(tables.TemplateColumn):
    attrs = {'td': {'class': 'text-end text-nowrap noprint min-width'}}
    template_code = """
    <a href="{% url 'plugins:netbox_config_backup:backup_config' pk=record.pk current=record.current.pk %}" class="btn btn-sm btn-outline-dark" title="View">
        <i class="mdi mdi-cloud-download"></i>
    </a>
    {% if record.previous %}
        <a href="{% url 'plugins:netbox_config_backup:backup_diff' pk=record.pk current=record.current.pk previous=record.previous.pk %}" class="btn btn-outline-dark btn-sm" title="Diff">
            <i class="mdi mdi-file-compare"></i>
        </a>
    {% else %}
        
    {% endif %}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, template_code=self.template_code, **kwargs)

    def header(self):
        return ''


class BackupTable(BaseTable):
    pk = columns.ToggleColumn()
    name = tables.Column(
        linkify=True,
        verbose_name='Backup Name'
    )
    device = tables.Column(
        linkify={
            'viewname': 'dcim:device',
            'args': [Accessor('device_id')],
        }
    )
    last_backup = tables.DateTimeColumn(
        orderable=False
    )
    next_attempt = tables.DateTimeColumn(
        orderable=False
    )

    class Meta(BaseTable.Meta):
        model = Backup
        fields = (
            'pk', 'name', 'device', 'last_backup', 'next_attempt', 'backup_count'
        )
        default_columns = (
            'pk', 'name', 'device', 'last_backup', 'next_attempt', 'backup_count'
        )


class BackupsTable(tables.Table):
    date = tables.Column()
    actions = ActionButtonsColumn()

    class Meta:
        attrs = {
            'class': 'table table-hover object-list',
        }
        order_by = ['-date']
