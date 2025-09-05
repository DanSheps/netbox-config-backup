import logging
from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from netbox.api.exceptions import ServiceUnavailable

logger = logging.getLogger("netbox_config_backup")


def napalm_init(device, ip=None, extra_args={}):
    from netbox import settings

    username = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get(
        'NAPALM_USERNAME', None
    )
    password = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get(
        'NAPALM_PASSWORD', None
    )
    timeout = settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {}).get(
        'NAPALM_TIMEOUT', None
    )
    optional_args = (
        settings.PLUGINS_CONFIG.get('netbox_napalm_plugin', {})
        .get('NAPALM_ARGS', [])
        .copy()
    )

    if device and device.platform and device.platform.napalm.napalm_args is not None:
        optional_args.update(device.platform.napalm.napalm_args)
    if extra_args != {}:
        optional_args.update(extra_args)

    # Check for primary IP address from NetBox object
    if ip is not None:
        host = str(ip.address.ip)
    elif device.primary_ip and device.primary_ip is not None:
        host = str(device.primary_ip.address.ip)
    else:
        raise ServiceUnavailable("This device does not have a primary IP address")

    # Check that NAPALM is installed
    try:
        import napalm
        from napalm.base.exceptions import ModuleImportError
    except ModuleNotFoundError as e:
        if getattr(e, 'name') == 'napalm':
            raise ServiceUnavailable(
                "NAPALM is not installed. Please see the documentation for instructions."
            )
        raise e

    # Validate the configured driver
    try:
        driver = napalm.get_network_driver(device.platform.napalm.napalm_driver)
    except ModuleImportError:
        raise ServiceUnavailable(
            "NAPALM driver for platform {} not found: {}.".format(
                device.platform, device.platform.napalm.napalm_driver
            )
        )

    # Connect to the device
    d = driver(
        hostname=host,
        username=username,
        password=password,
        timeout=timeout,
        optional_args=optional_args,
    )
    try:
        d.open()
    except Exception as e:
        if isinstance(e, NetmikoAuthenticationException):
            logger.info(f'Authentication error for f{device}:{host}')
            logger.info(f'{e}')
        elif isinstance(e, NetmikoTimeoutException):
            logger.info('Connection error')
        raise ServiceUnavailable(
            "Error connecting to the device at {}: {}".format(host, e)
        )

    return d
