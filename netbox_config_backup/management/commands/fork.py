import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from netbox_config_backup.models import BackupJob
from netbox_config_backup.tasks import backup_job
from netbox_config_backup.utils import remove_queued
from netbox_config_backup.utils.rq import can_backup


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--time', dest='time', help="time")
        parser.add_argument('--device', dest='device', help="Device Name")

    def handle(self, *args, **options):
        from multiprocessing import Process
        import time
        def test(i):
            self.stdout.write(f"Child {i} is running")
            self.stdout.write(f"Child {i} sleeping 10 seconds")
            time.sleep(10)
            self.stdout.write(f"Child {i} sleep complete")

        processes = {}
        for i in range(1, 3):
            p = Process(target=test, args=(i,))
            p.start()
            p.join(1)
            self.stdout.write(f"Child {i} running")
            processes.update({p.pid: p})

        while True:
            if len(processes) == 0:
                break
            for pid in list(processes.keys()):
                process = processes.get(pid, None)
                if not process.is_alive():
                    del processes[pid]
            time.sleep(1)




