import logging
import sys


def get_logger():
    # Setup logging to Stdout
    formatter = logging.Formatter('[%(asctime)s][%(levelname)s] - %(message)s')
    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setLevel(logging.DEBUG)
    stdouthandler.setFormatter(formatter)
    logger = logging.getLogger("netbox_config_backup")
    logger.addHandler(stdouthandler)

    return logger
