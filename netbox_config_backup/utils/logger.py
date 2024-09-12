import logging
import sys


def get_logger():
    # Setup logging to Stdout
    formatter = logging.Formatter(f'[%(asctime)s][%(levelname)s] - %(message)s')
    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setLevel(logging.DEBUG)
    stdouthandler.setFormatter(formatter)
    logger = logging.getLogger(f"netbox_config_backup")
    logger.addHandler(stdouthandler)

    return logger
