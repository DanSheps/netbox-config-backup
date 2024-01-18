from netbox.plugins import PluginMenuItem, PluginMenuButton, PluginMenu
from utilities.choices import ButtonColorChoices

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
    ]
)

unassigned = PluginMenuItem(
    link='plugins:netbox_config_backup:unassignedbackup_list',
    link_text='Unassigned Backups',
    permissions=['netbox_config_backup.view_backups'],
    buttons=[]
)

menu = PluginMenu(
    label="Configuration Backup",
    groups=(
        ('Backup Jobs', (assigned, unassigned)),
    )
)
