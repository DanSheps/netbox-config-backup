import django_tables2 as tables
from django_tables2.utils import Accessor

from netbox_config_backup.models import Backup, BackupCommitTreeChange, BackupJob
from netbox.tables import columns, BaseTable, NetBoxTable


class ActionButtonsColumn(tables.TemplateColumn):
    attrs = {'td': {'class': 'text-end text-nowrap noprint min-width'}}
    template_code = """
    <a href="{% url 'plugins:netbox_config_backup:backup_compliance' backup=record.backup.pk current=record.pk %}" class="btn btn-sm btn-outline-dark" title="View">
        <i class="mdi mdi-check-all"></i>
    </a>
    <a href="{% url 'plugins:netbox_config_backup:backup_config' backup=record.backup.pk current=record.pk %}" class="btn btn-sm btn-outline-dark" title="View">
        <i class="mdi mdi-cloud-download"></i>
    </a>
    {% if record.previous %}
        <a href="{% url 'plugins:netbox_config_backup:backup_diff' backup=record.backup.pk current=record.pk previous=record.previous.pk %}" class="btn btn-outline-dark btn-sm" title="Diff">
            <i class="mdi mdi-file-compare"></i>
        </a>
    {% else %}
        
    {% endif %}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, template_code=self.template_code, **kwargs)

    def header(self):
        return ''


class BackupJobTable(BaseTable):
    id = tables.Column(
        linkify=True,
        verbose_name='ID'
    )
    pk = columns.ToggleColumn(

    )
    backup = tables.Column(
        linkify=True,
        verbose_name='Backup'
    )
    created = tables.DateTimeColumn()
    scheduled = tables.DateTimeColumn()
    started = tables.DateTimeColumn()
    completed = tables.DateTimeColumn()

    class Meta(BaseTable.Meta):
        model = BackupJob
        fields = (
            'pk', 'id', 'backup', 'pid', 'created', 'scheduled', 'started', 'completed', 'status'
        )
        default_columns = (
            'pk', 'backup', 'pid', 'created', 'scheduled', 'started', 'completed', 'status'
        )

    def render_backup_count(self, value):
        return f'{value.count()}'


class BackupTable(BaseTable):
    pk = columns.ToggleColumn(

    )
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
    last_backup = tables.DateTimeColumn()
    next_attempt = tables.DateTimeColumn()
    last_change = tables.DateTimeColumn()
    backup_count = tables.Column(
        accessor='changes'
    )
    config_status = tables.BooleanColumn(
        verbose_name='Config Saved'
    )

    class Meta(BaseTable.Meta):
        model = Backup
        fields = (
            'pk', 'name', 'device', 'last_backup', 'next_attempt', 'last_change', 'backup_count'
        )
        default_columns = (
            'pk', 'name', 'device', 'last_backup', 'next_attempt', 'backup_count'
        )

    def render_backup_count(self, value):
        return f'{value.count()}'


class BackupsTable(NetBoxTable):
    date = tables.Column(
        accessor='commit__time'
    )
    type = tables.Column(
        accessor='file__type'
    )
    actions = ActionButtonsColumn()

    class Meta:
        model = BackupCommitTreeChange
        fields = (
            'pk', 'id', 'date', 'type', 'backup', 'commit', 'file', 'actions'
        )
        default_columns = (
            'pk', 'id', 'date', 'type', 'actions'
        )
        attrs = {
            'class': 'table table-hover object-list',
        }
        order_by = ['-date']
