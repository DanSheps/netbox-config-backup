from extras.plugins import PluginMenuItem, PluginMenuButton, PluginMenu
from utilities.choices import ButtonColorChoices

item = PluginMenuItem(
        link='plugins:netbox_config_backup:backup_list',
        link_text='Devices',
        buttons=[
            PluginMenuButton(
                link="plugins:netbox_config_backup:backup_add",
                title="Add",
                icon_class="mdi mdi-plus",
                color=ButtonColorChoices.GREEN,
            ),
        ]
    )

menu = PluginMenu(
        label="Configuration Backup",
        groups=(
            ('Backup Jobs', (item,)),
        )
    )
