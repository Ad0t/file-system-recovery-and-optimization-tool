"""Tests for the DirectoryNode and DirectoryTree classes."""

import pytest
from backend.src.core.directory import DirectoryNode, DirectoryTree


class TestDirectoryNode:
    """Test suite for DirectoryNode."""

    def test_file_node(self):
        node = DirectoryNode("test.txt", is_directory=False)
        assert node.name == "test.txt"
        assert node.is_directory is False

    def test_directory_node(self):
        node = DirectoryNode("subdir", is_directory=True)
        assert node.is_directory is True


class TestDirectoryTree:
    """Test suite for DirectoryTree."""

    def test_add_entry(self):
        tree = DirectoryTree()
        result = tree.create_directory("/mydir")
        assert result is True
        assert tree.resolve_path("/mydir") is not None

    def test_add_duplicate_entry(self):
        tree = DirectoryTree()
        tree.create_directory("/mydir")
        # Creating the same directory again should succeed (mkdir -p behavior)
        result = tree.create_directory("/mydir")
        assert result is True

    def test_remove_entry(self):
        tree = DirectoryTree()
        tree.create_directory("/mydir")
        removed = tree.delete("/mydir")
        assert removed is True
        assert tree.resolve_path("/mydir") is None

    def test_remove_nonexistent(self):
        tree = DirectoryTree()
        assert tree.delete("/nope") is False

    def test_get_entry(self):
        tree = DirectoryTree()
        tree.create_directory("/mydir")
        node = tree.resolve_path("/mydir")
        assert node is not None
        assert node.name == "mydir"

    def test_list_entries(self):
        tree = DirectoryTree()
        tree.create_directory("/a")
        tree.create_directory("/b")
        entries = tree.list_directory("/")
        assert len(entries) == 2

    def test_get_path_root(self):
        tree = DirectoryTree()
        assert tree.root.get_full_path() == "/"

    def test_get_path_nested(self):
        tree = DirectoryTree()
        tree.create_directory("/home/user")
        node = tree.resolve_path("/home/user")
        assert node.get_full_path() == "/home/user"
