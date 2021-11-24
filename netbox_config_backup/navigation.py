from extras.plugins import PluginMenuItem, PluginMenuButton, ButtonColorChoices

menu_items = (
    PluginMenuItem(
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
    ),
)