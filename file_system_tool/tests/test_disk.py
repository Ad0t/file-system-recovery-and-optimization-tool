"""Tests for the Disk class."""

import pytest
from src.core.disk import Disk


class TestDisk:
    """Test suite for Disk."""

    def test_disk_initialization(self):
        disk = Disk(num_blocks=10, block_size=512)
        assert disk.num_blocks == 10
        assert disk.block_size == 512

    def test_read_empty_block(self):
        disk = Disk(num_blocks=10, block_size=512)
        data = disk.read_block(0)
        assert data == bytearray(512)

    def test_write_and_read_block(self):
        disk = Disk(num_blocks=10, block_size=512)
        test_data = b"Hello, File System!"
        disk.write_block(0, test_data)
        data = disk.read_block(0)
        assert data[:len(test_data)] == test_data

    def test_write_block_padding(self):
        disk = Disk(num_blocks=10, block_size=512)
        disk.write_block(0, b"short")
        data = disk.read_block(0)
        assert len(data) == 512
        assert data[5:] == bytearray(507)

    def test_clear_block(self):
        disk = Disk(num_blocks=10, block_size=512)
        disk.write_block(0, b"data")
        disk.clear_block(0)
        assert disk.read_block(0) == bytearray(512)

    def test_invalid_block_read(self):
        disk = Disk(num_blocks=10, block_size=512)
        with pytest.raises(IndexError):
            disk.read_block(10)

    def test_invalid_block_write(self):
        disk = Disk(num_blocks=10, block_size=512)
        with pytest.raises(IndexError):
            disk.write_block(-1, b"data")

    def test_disk_usage(self):
        disk = Disk(num_blocks=10, block_size=512)
        assert disk.get_disk_usage() == 0.0
        disk.write_block(0, b"data")
        assert disk.get_disk_usage() == 10.0

    def test_repr(self):
        disk = Disk(num_blocks=10, block_size=512)
        assert "num_blocks=10" in repr(disk)
