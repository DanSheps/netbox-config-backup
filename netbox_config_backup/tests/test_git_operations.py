import os
import tempfile
import shutil
from django.test import TestCase
from unittest.mock import patch

from netbox_config_backup.git import GitBackup


class TestGitRepository(TestCase):
    """Tests for Git repository operations"""

    def setUp(self):
        """Set up a temporary repository for testing"""
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()

        # Mock get_repository_dir to return temp dir
        self.patcher = patch.object(GitBackup, 'get_repository_dir', return_value=self.temp_dir)
        self.mock_get_repo_dir = self.patcher.start()

    def tearDown(self):
        """Clean up temporary repository"""
        self.patcher.stop()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_git_backup_initialization(self):
        """Test GitBackup initializes repository correctly"""
        git_backup = GitBackup()

        self.assertIsNotNone(git_backup.repository, "Repository should be initialized")
        self.assertIsNotNone(git_backup.location, "Location should be set")
        self.assertTrue(os.path.exists(git_backup.location), "Repository directory should exist")

    def test_git_backup_write_creates_file(self):
        """Test that write() creates files correctly"""
        git_backup = GitBackup()

        filename = 'test_config.running'
        content = 'Test configuration content'

        git_backup.write(filename, content)

        filepath = os.path.join(git_backup.location, filename)
        self.assertTrue(os.path.exists(filepath), "File should be created")

        with open(filepath, 'r') as f:
            read_content = f.read()

        self.assertEqual(read_content, content, "File content should match")

    def test_git_backup_write_multiple_files(self):
        """Test writing multiple configuration files"""
        git_backup = GitBackup()

        files = {
            'device1.running': 'Running config 1',
            'device1.startup': 'Startup config 1',
            'device2.running': 'Running config 2',
            'device2.startup': 'Startup config 2',
        }

        for filename, content in files.items():
            git_backup.write(filename, content)

        # Verify all files exist
        for filename in files.keys():
            filepath = os.path.join(git_backup.location, filename)
            self.assertTrue(os.path.exists(filepath), f"File {filename} should exist")

        # Verify directory structure is correct
        repo_files = os.listdir(git_backup.location)
        self.assertEqual(len([f for f in repo_files if f.endswith('.running')]), 2)
        self.assertEqual(len([f for f in repo_files if f.endswith('.startup')]), 2)

    def test_construct_path_prevents_traversal(self):
        """Test _construct_path() prevents directory traversal attacks"""
        git_backup = GitBackup()

        # Valid path should work
        valid_path = git_backup._construct_path('device.running')
        self.assertTrue(valid_path.startswith(git_backup.location))

        # Path traversal attempt should raise ValueError
        with self.assertRaises(ValueError):
            git_backup._construct_path('../../../etc/passwd')

        with self.assertRaises(ValueError):
            git_backup._construct_path('../../dangerous')

    def test_git_backup_read_nonexistent_file(self):
        """Test reading a nonexistent file returns None"""
        git_backup = GitBackup()

        result = git_backup.read('nonexistent_file.running')

        self.assertIsNone(result, "Reading nonexistent file should return None")

    def test_git_backup_status(self):
        """Test repository status tracking"""
        git_backup = GitBackup()

        # Write a file
        git_backup.write('test.running', 'Test content')

        # Get status - should track the new file
        status = git_backup.status()
        self.assertIsNotNone(status, "Status should return repository status")

