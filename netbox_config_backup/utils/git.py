import difflib
import re
import logging
from deepdiff import DeepDiff

logger = logging.getLogger(f"netbox_config_backup")


class Differ(DeepDiff):
    def is_diff(self):
        if self.get('values_changed'):
            return True
        return False

    def diff(self):
        diff = self.get('values_changed', {}).get('root', {}).get('diff', '')
        return diff

    def compare(self):
        diff = self.diff()
        return diff.splitlines()

    def cisco_compare(self):
        return self.compare()
