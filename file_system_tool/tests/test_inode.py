"""Tests for the Inode class."""

import pytest
from backend.src.core.inode import Inode


class TestInode:
    """Test suite for Inode."""

    def test_inode_creation_file(self):
        inode = Inode(inode_number=1, file_type="file")
        assert inode.file_type == "file"
        assert inode.size_bytes == 0
        assert inode.link_count == 1

    def test_inode_creation_directory(self):
        inode = Inode(inode_number=2, file_type="directory")
        assert inode.file_type == "directory"

    def test_invalid_file_type(self):
        with pytest.raises(ValueError):
            Inode(inode_number=1, file_type="invalid")

    def test_add_block_pointer(self):
        inode = Inode(inode_number=1)
        assert inode.add_block_pointer(5) is True
        assert 5 in inode.direct_pointers

    def test_remove_block_pointer(self):
        inode = Inode(inode_number=1)
        inode.add_block_pointer(5)
        # direct_pointers is a list, remove by value
        inode.direct_pointers.remove(5)
        assert 5 not in inode.direct_pointers

    def test_timestamps_updated(self):
        inode = Inode(inode_number=1)
        initial_time = inode.modified_time
        inode.add_block_pointer(0)
        assert inode.modified_time >= initial_time

    def test_update_size(self):
        inode = Inode(inode_number=1)
        inode.update_size(8192)
        assert inode.size_bytes == 8192
        assert inode.block_count == 2  # 8192 / 4096

    def test_negative_size_raises(self):
        inode = Inode(inode_number=1)
        with pytest.raises(ValueError):
            inode.update_size(-1)

    def test_direct_pointer_limit(self):
        inode = Inode(inode_number=1)
        for i in range(12):
            assert inode.add_block_pointer(i) is True
        # 13th should fail
        assert inode.add_block_pointer(12) is False

    def test_to_dict_and_from_dict(self):
        inode = Inode(inode_number=1, file_type="file", size=4096)
        inode.add_block_pointer(10)
        data = inode.to_dict()
        restored = Inode.from_dict(data)
        assert restored.inode_number == 1
        assert restored.size_bytes == 4096
        assert 10 in restored.direct_pointers

    def test_repr(self):
        inode = Inode(inode_number=1, file_type="file")
        assert "num=1" in repr(inode)
