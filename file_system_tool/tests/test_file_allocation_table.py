"""Tests for the FileAllocationTable class."""

import pytest
from src.core.file_allocation_table import FileAllocationTable
from src.utils.constants import FAT_FREE, FAT_EOF, FAT_BAD


class TestFileAllocationTable:
    """Test suite for FileAllocationTable."""

    def test_initialization(self):
        fat = FileAllocationTable(num_blocks=10)
        assert fat.num_blocks == 10
        assert fat.free_count == 10

    def test_allocate_chain(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([0, 1, 2])
        assert fat.table[0] == 1
        assert fat.table[1] == 2
        assert fat.table[2] == FAT_EOF

    def test_get_chain(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([3, 5, 7])
        chain = fat.get_chain(3)
        assert chain == [3, 5, 7]

    def test_free_chain(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([0, 1, 2])
        freed = fat.free_chain(0)
        assert freed == [0, 1, 2]
        assert all(fat.is_free(b) for b in [0, 1, 2])

    def test_mark_bad(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.mark_bad(5)
        assert fat.is_bad(5) is True

    def test_is_free(self):
        fat = FileAllocationTable(num_blocks=10)
        assert fat.is_free(0) is True

    def test_is_eof(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([0])
        assert fat.is_eof(0) is True

    def test_empty_chain(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([])  # Should not raise

    def test_single_block_chain(self):
        fat = FileAllocationTable(num_blocks=10)
        fat.allocate_chain([4])
        chain = fat.get_chain(4)
        assert chain == [4]
        assert fat.is_eof(4) is True

    def test_circular_chain_protection(self):
        fat = FileAllocationTable(num_blocks=10)
        # Manually create a circular chain
        fat.table[0] = 1
        fat.table[1] = 0  # Points back to 0
        chain = fat.get_chain(0)
        assert len(chain) == 2  # Should stop at visited block
