import os
from datetime import datetime
from fnmatch import fnmatch

from django.utils import timezone
from time import sleep

from deepdiff import DeepDiff
from dulwich import repo, porcelain, object_store
from pydriller import Git

from netbox import settings

__all__ = 'repository'

from netbox.plugins import get_plugin_config


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

        self.location = self.get_repository_dir()

        try:
            # Try to open existing repository
            self.repository = repo.Repo(self.location)
        except FileNotFoundError:
            # If directory doesn't exist or isn't a valid git repo, initialize it
            self.repository = repo.Repo.init(path=self.location, mkdir=True)
        except repo.NotGitRepository:
            # If the directory exists but isn't a git repo, initialize it
            self.repository = repo.Repo.init(path=self.location)

        if self.repository is not None:
            try:
                self.driller = Git(self.location)
            except OSError:
                pass

    @staticmethod
    def get_repository_dir():
        repository = get_plugin_config("netbox_config_backup", 'repository')
        if repository == os.path.abspath(repository) or repository == (os.path.abspath(repository) + os.path.sep):
            return repository

        return f'{os.path.dirname(os.path.dirname(settings.BASE_DIR))}{os.path.sep}{repository}'

    def _construct_path(self, file):
        path = os.path.join(self.location, file)
        if not os.path.realpath(path).startswith(os.path.realpath(self.location)):
            raise ValueError("File path is outside the repository")
        return path

    def add(self, file):
        path = self._construct_path(file)
        porcelain.add(self.repository, path)

    def write(self, file, data):
        path = self._construct_path(file)
        with open(path, 'w') as f:
            f.write(data)

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

    def status(self):
        return porcelain.status(self.repository)

    def commit(self, message):
        # Check for untracked or unstaged files that match the patterns for running and startup configs
        status = porcelain.status(self.repository)
        staged = []
        for file in status.unstaged:
            if isinstance(file, bytes):
                file = file.decode('ascii')
            self.add(file)
            staged.append(file)
        for file in status.untracked:
            if isinstance(file, bytes):
                file = file.decode('ascii')
            self.add(file)
            staged.append(file)
        staged.extend(status.staged.get('add'))
        staged.extend(status.staged.get('delete'))
        staged.extend(status.staged.get('modify'))
        if not staged:
            return None

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
            except repo.InvalidUserIdentity:
                committer = 'Your NetBox is misconfigured <netbox@localhost>'.encode('ascii')
                author = 'Your NetBox is misconfigured <netbox@localhost>'.encode('ascii')
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
            _, sha = object_store.tree_lookup_path(self.repository.__getitem__, tree, path)
            data = self.repository[sha].data.decode('ascii')
            return data
        except KeyError:
            return None

    def diff(self, file, a=None, b=None):
        _ = file.encode('ascii')
        commits = [a, b]
        data = []
        for commit in commits:
            if commit is None:
                data.append(None)
            else:
                data.append(self.read(file, commit))

        diff = DeepDiff(data[0], data[1]).diff()
        return diff

    def log(self, file=None, paths=None, index=None, depth=None, uuid=None):
        tz = timezone.now().astimezone().tzinfo
        if file is not None:
            path = file.encode('ascii')
            uuid = None
            paths = [path]
        elif paths is not None:
            path = None
            uuid = None
            for idx in range(0, len(paths)):
                path = paths[idx]
                paths[idx] = path.encode('ascii')
        else:
            path = None

        if index == 'HEAD':
            index = self.repository.head()
        elif index is not None:
            index = index.encode('ascii')

        walker = self.repository.get_walker(include=index, paths=paths, max_entries=depth)
        entries = [entry for entry in walker]

        indexes = []
        for entry in entries:
            encoding = entry.commit.encoding.decode('ascii') if entry.commit.encoding else 'ascii'
            output = {
                'author': decode(entry.commit.author, encoding),
                'committer': decode(entry.commit.committer, encoding),
                'message': decode(entry.commit.message, encoding),
                'parents': [decode(parent, encoding) for parent in entry.commit.parents],
                'sha': str(entry.commit.sha().hexdigest()),
                'time': datetime.fromtimestamp(entry.commit.commit_time, tz=tz),
                'tree': decode(entry.commit.tree, encoding),
            }
            changes = []
            for change in entry.changes():
                old = {
                    'sha': decode(getattr(change.old, 'sha', None), encoding),
                    'path': decode(getattr(change.old, 'path', None), encoding),
                }
                if path is not None and (old.get('path') == path or change.get('new') == path):
                    output.update(
                        {
                            'change': {
                                'type': change.type,
                                'old': {
                                    'path': old.get('path'),
                                    'sha': old.get('sha'),
                                },
                                'new': {
                                    'path': decode(getattr(change.new, 'path', None), encoding),
                                    'sha': decode(getattr(change.new, 'sha', None), encoding),
                                },
                            }
                        }
                    )
                changes.append(
                    {
                        'type': change.type,
                        'old': {
                            'path': decode(getattr(change.old, 'path', None), encoding),
                            'sha': decode(getattr(change.old, 'sha', None), encoding),
                        },
                        'new': {
                            'path': decode(getattr(change.new, 'path', None), encoding),
                            'sha': decode(getattr(change.new, 'sha', None), encoding),
                        },
                    }
                )

            output.update({'changes': changes})

            uuids = []
            if uuid is None:
                indexes.append(output)
            elif uuid is not None:
                uuids = set(
                    [
                        change.get('old', {}).get('path').split('.')[0]
                        for change in changes
                        if change.get('old', {}).get('path') is not None
                    ]
                    + [
                        change.get('new', {}).get('path').split('.')[0]
                        for change in changes
                        if change.get('new', {}).get('path') is not None
                    ]
                )
                if str(uuid) in uuids:
                    indexes.append(output)
        return indexes


repository = GitBackup()
