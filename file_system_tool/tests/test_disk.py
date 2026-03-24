"""Tests for the Disk class."""

import pytest
import os
from src.core.disk import Disk
from src.utils.constants import FileSystemConfig


class TestDisk:
    """Test suite for Disk."""

    def test_disk_initialization(self):
        disk = Disk(total_blocks=10, block_size=512)
        assert disk.total_blocks == 10
        assert disk.block_size == 512

    def test_read_empty_block(self):
        disk = Disk(total_blocks=10, block_size=512)
        data = disk.read_block(0)
        assert data is None

    def test_write_and_read_block(self):
        disk = Disk(total_blocks=10, block_size=512)
        test_data = b"Hello, File System!"
        assert disk.write_block(0, test_data) is True
        data = disk.read_block(0)
        assert data == test_data

    def test_write_block_no_padding(self):
        disk = Disk(total_blocks=10, block_size=512)
        disk.write_block(0, b"short")
        data = disk.read_block(0)
        assert len(data) == 5
        assert data == b"short"

    def test_format_disk(self):
        disk = Disk(total_blocks=10, block_size=512)
        disk.write_block(0, b"data")
        disk.format_disk()
        assert disk.read_block(0) is None

    def test_invalid_block_read(self):
        disk = Disk(total_blocks=10, block_size=512)
        with pytest.raises(IndexError):
            disk.read_block(10)

    def test_invalid_block_write(self):
        disk = Disk(total_blocks=10, block_size=512)
        with pytest.raises(IndexError):
            disk.write_block(-1, b"data")

    def test_disk_usage(self):
        disk = Disk(total_blocks=10, block_size=512)
        info = disk.get_disk_info()
        assert info["blocks_used"] == 0
        disk.write_block(0, b"data")
        info = disk.get_disk_info()
        assert info["blocks_used"] == 1
        assert info["total_writes"] == 1

    def test_repr(self):
        disk = Disk(total_blocks=10, block_size=512)
        assert "total_blocks=10" in repr(disk)
