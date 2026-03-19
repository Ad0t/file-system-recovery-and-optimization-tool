"""Tests for the Directory and DirectoryEntry classes."""

import pytest
from src.core.directory import Directory, DirectoryEntry
from src.utils.constants import INODE_TYPE_FILE, INODE_TYPE_DIRECTORY


class TestDirectoryEntry:
    """Test suite for DirectoryEntry."""

    def test_file_entry(self):
        entry = DirectoryEntry("test.txt", inode_id=1, entry_type=INODE_TYPE_FILE)
        assert entry.name == "test.txt"
        assert entry.is_file is True
        assert entry.is_directory is False

    def test_directory_entry(self):
        entry = DirectoryEntry("subdir", inode_id=2, entry_type=INODE_TYPE_DIRECTORY)
        assert entry.is_directory is True


class TestDirectory:
    """Test suite for Directory."""

    def test_add_entry(self):
        d = Directory("root", inode_id=0)
        entry = d.add_entry("file.txt", inode_id=1)
        assert entry is not None
        assert len(d) == 1

    def test_add_duplicate_entry(self):
        d = Directory("root", inode_id=0)
        d.add_entry("file.txt", inode_id=1)
        assert d.add_entry("file.txt", inode_id=2) is None

    def test_remove_entry(self):
        d = Directory("root", inode_id=0)
        d.add_entry("file.txt", inode_id=1)
        removed = d.remove_entry("file.txt")
        assert removed is not None
        assert len(d) == 0

    def test_remove_nonexistent(self):
        d = Directory("root", inode_id=0)
        assert d.remove_entry("nope.txt") is None

    def test_get_entry(self):
        d = Directory("root", inode_id=0)
        d.add_entry("file.txt", inode_id=1)
        entry = d.get_entry("file.txt")
        assert entry.name == "file.txt"

    def test_list_entries(self):
        d = Directory("root", inode_id=0)
        d.add_entry("a.txt", inode_id=1)
        d.add_entry("b.txt", inode_id=2)
        entries = d.list_entries()
        assert len(entries) == 2

    def test_get_path_root(self):
        d = Directory("root", inode_id=0, parent=None)
        assert d.get_path() == "/"

    def test_get_path_nested(self):
        root = Directory("root", inode_id=0, parent=None)
        child = Directory("home", inode_id=1, parent=root)
        grandchild = Directory("user", inode_id=2, parent=child)
        assert grandchild.get_path() == "/home/user"
