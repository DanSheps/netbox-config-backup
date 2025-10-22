from django.utils.translation import gettext as _

from netbox.object_actions import ObjectAction

__all__ = (
    'DiffAction',
    'ViewConfigAction',
    'BulkConfigAction',
    'BulkDiffAction',
    'RunBackupsNowAction',
)


class DiffAction(ObjectAction):
    """
    Create a new object.
    """

    name = 'diff'
    label = _('Diff')
    permissions_required = {'view'}
    template_name = 'netbox_config_backup/buttons/diff.html'


class ViewConfigAction(ObjectAction):
    """
    Create a new object.
    """

    name = 'config'
    label = _('Config')
    permissions_required = {'view'}
    template_name = 'netbox_config_backup/buttons/diff.html'


class BulkConfigAction(ObjectAction):
    name = 'bulk_config'
    label = _('Bulk View Config')
    multi = True
    permissions_required = {'view'}
    template_name = 'netbox_config_backup/buttons/config.html'


class BulkDiffAction(ObjectAction):
    name = 'bulk_diff'
    label = _('Bulk Diff')
    multi = True
    permissions_required = {'view'}
    template_name = 'netbox_config_backup/buttons/diff.html'


class RunBackupsNowAction(ObjectAction):
    name = 'run'
    label = _('Run Now')
    permissions_required = {'view'}
    template_name = 'netbox_config_backup/buttons/diff.html'
