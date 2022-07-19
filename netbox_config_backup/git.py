import os
import difflib
from datetime import datetime
from time import sleep

from dulwich import repo, porcelain, object_store
from pydriller import Git

from netbox import settings

__all__ = (
    'repository'
)

from netbox_config_backup.helpers import get_repository_dir


def encode(value, encoding):
    if value is not None:
        return value.encode(encoding)
    return None


def decode(value, encoding):
    if value is not None:
        return value.decode(encoding)
    return None


class GitBackup:
    repository = None
    driller = None
    location = None

    def __init__(self):
        self.location = get_repository_dir()

        if os.path.exists(self.location):
            self.repository = repo.Repo(self.location)

        if self.repository is None:
            self.repository = repo.Repo.init(self.location, True)

        if self.repository is not None:
            try:
                self.driller = Git(self.location)
            except OSError:
                pass

    def write(self, file, data):
        path = f'{self.location}{os.path.sep}{file}'
        with open(path, 'w') as f:
            f.write(data)
            f.close()

        failures = 0
        while failures < 10:
            try:
                porcelain.add(self.repository, path)
                return
            except FileExistsError:
                sleep(1)
                failures = failures + 1
                if failures >= 10:
                    raise Exception('Unable to acquire lock on repository in a timely manner')


    def commit(self, message):
        committer = settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('committer', None)
        author = settings.PLUGINS_CONFIG.get('netbox_config_backup', {}).get('author', None)

        if author is not None:
            author = author.encode('ascii')
        if committer is not None:
            committer = committer.encode('ascii')

        failures = 0
        while failures < 10:
            try:
                commit = porcelain.commit(self.repository, message, committer=committer, author=author)
                return commit.decode('ascii')
            except FileExistsError:
                sleep(1)
                failures = failures + 1
                if failures >= 10:
                    raise Exception('Unable to acquire lock on repository in a timely manner')

    def read(self, file, index=None):
        path = file.encode('ascii')
        if index is None:
            index = 'HEAD'

        try:
            tree = self.repository[index.encode('ascii')].tree
            mode, sha = object_store.tree_lookup_path(self.repository.__getitem__, tree, path)
            data = self.repository[sha].data.decode('ascii')
            return data
        except KeyError:
            return None

    def diff(self, file, a=None, b=None):
        path = file.encode('ascii')
        commits = [a, b]
        data = []
        for commit in commits:
            if commit is None:
                data.append(None)
            else:
                data.append(self.read(file, commit))

        diff = DeepDiff(data[0], data[1]).diff()
        return diff

    def log(self, file=None, paths=[], index=None, depth=None):
        def get_index(haystack, needle):
            key = f'{needle.file}'

        if file is not None:
            path = file.encode('ascii')
            paths = [path]
        else:
            path = None
            for idx in range(0, len(paths)):
                path = paths[idx]
                paths[idx] = path.encode('ascii')

        if index is not None:
            index = index.encode('ascii')

        walker = self.repository.get_walker(include=index, paths=paths, max_entries=depth)
        entries = [entry for entry in walker]

        indexes = []
        for entry in entries:
            output = {}
            encoding = entry.commit.encoding.decode('ascii') if entry.commit.encoding else 'ascii'
            parents = []
            output = {
                'author': decode(entry.commit.author, encoding),
                'committer': decode(entry.commit.committer, encoding),
                'message': decode(entry.commit.message, encoding),
                'parents': [decode(parent, encoding) for parent in entry.commit.parents],
                'sha': str(entry.commit.sha().hexdigest()),
                'time': datetime.fromtimestamp(entry.commit.commit_time),
                'tree': decode(entry.commit.tree, encoding)
            }
            changes = []
            for change in entry.changes():
                old = {'sha': decode(change.old.sha, encoding), 'path': decode(change.old.path, encoding)}
                if path is not None and (change.old.path == path or change.new.path == path):
                    output.update({
                        'change': {
                            'type': change.type,
                            'old': {
                                'path': old.get('path'),
                                'sha': old.get('sha'),
                            },
                            'new': {
                                'path': decode(change.new.path, encoding),
                                'sha': decode(change.new.sha, encoding)
                            },
                        }
                    })
                changes.append({
                    'type': change.type,
                    'old': {
                        'path': decode(change.old.path, encoding),
                        'sha': decode(change.old.sha, encoding)
                    },
                    'new': {
                        'path': decode(change.new.path, encoding),
                        'sha': decode(change.new.sha, encoding)
                    },
                })

            output.update({'changes': changes})
            indexes.append(output)

        return indexes


repository = GitBackup()
