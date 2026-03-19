"""Tests for the Inode and InodeTable classes."""

import pytest
from src.core.inode import Inode, InodeTable
from src.utils.constants import INODE_TYPE_FILE, INODE_TYPE_DIRECTORY


class TestInode:
    """Test suite for Inode."""

    def test_inode_creation(self):
        inode = Inode(INODE_TYPE_FILE)
        assert inode.inode_type == INODE_TYPE_FILE
        assert inode.size == 0
        assert inode.link_count == 1
        assert inode.is_file is True
        assert inode.is_directory is False

    def test_directory_inode(self):
        inode = Inode(INODE_TYPE_DIRECTORY)
        assert inode.is_directory is True
        assert inode.is_file is False

    def test_add_block(self):
        inode = Inode()
        assert inode.add_block(5) is True
        assert 5 in inode.direct_blocks

    def test_remove_block(self):
        inode = Inode()
        inode.add_block(5)
        inode.remove_block(5)
        assert 5 not in inode.direct_blocks

    def test_timestamps_updated(self):
        inode = Inode()
        initial_time = inode.modified_at
        inode.add_block(0)
        assert inode.modified_at >= initial_time


class TestInodeTable:
    """Test suite for InodeTable."""

    def test_allocate_inode(self):
        table = InodeTable(max_inodes=10)
        inode = table.allocate_inode(INODE_TYPE_FILE)
        assert inode is not None
        assert len(table) == 1

    def test_free_inode(self):
        table = InodeTable(max_inodes=10)
        inode = table.allocate_inode()
        assert table.free_inode(inode.inode_id) is True
        assert len(table) == 0

    def test_get_inode(self):
        table = InodeTable(max_inodes=10)
        inode = table.allocate_inode()
        fetched = table.get_inode(inode.inode_id)
        assert fetched is inode

    def test_max_inodes(self):
        table = InodeTable(max_inodes=2)
        table.allocate_inode()
        table.allocate_inode()
        assert table.allocate_inode() is None

    def test_free_nonexistent(self):
        table = InodeTable()
        assert table.free_inode(999) is False
