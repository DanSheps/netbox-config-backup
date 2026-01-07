from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu

jobs = PluginMenuItem(
    link='plugins:netbox_config_backup:backupjob_list',
    link_text='Jobs',
    permissions=['netbox_config_backup.view_backups'],
    buttons=[],
)

assigned = PluginMenuItem(
    link='plugins:netbox_config_backup:backup_list',
    link_text='Devices',
    permissions=['netbox_config_backup.view_backups'],
    buttons=[
        PluginMenuButton(
            link="plugins:netbox_config_backup:backup_add",
            title="Add",
            icon_class="mdi mdi-plus",
            color=ButtonColorChoices.GREEN,
        ),
    ],
)

unassigned = PluginMenuItem(
    link='plugins:netbox_config_backup:backup_unassigned_list',
    link_text='Unassigned Backups',
    permissions=['netbox_config_backup.view_backups'],
    buttons=[],
)

menu = PluginMenu(
    label="Configuration Backup",
    groups=(
        ('Backup Jobs', (jobs,)),
        ('Backups', (assigned, unassigned)),
    ),
)
