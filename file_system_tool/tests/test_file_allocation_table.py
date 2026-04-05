"""Tests for the FileAllocationTable class."""

import pytest
from backend.src.core.file_allocation_table import FileAllocationTable


class TestFileAllocationTable:
    """Test suite for FileAllocationTable."""

    def test_initialization(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        assert fat.allocation_method == "contiguous"
        assert len(fat.file_to_blocks) == 0

    def test_allocate_contiguous(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        assert fat.allocate(100, [0, 1, 2]) is True
        assert fat.get_file_blocks(100) == [0, 1, 2]
        assert fat.get_block_owner(1) == 100

    def test_allocate_linked(self):
        fat = FileAllocationTable(allocation_method="linked")
        assert fat.allocate(101, [3, 5, 7]) is True
        chain = fat.follow_linked_chain(3)
        assert chain == [3, 5, 7]

    def test_allocate_indexed(self):
        fat = FileAllocationTable(allocation_method="indexed")
        assert fat.allocate(102, [2, 8, 4]) is True
        assert fat.get_file_blocks(102) == [2, 8, 4]

    def test_deallocate(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        fat.allocate(100, [0, 1, 2])
        freed = fat.deallocate(100)
        assert freed == [0, 1, 2]
        assert fat.get_block_owner(1) is None

    def test_invalid_contiguous(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        # Blocks must be sequential for contiguous
        assert fat.allocate(100, [0, 2]) is False

    def test_block_already_owned(self):
        fat = FileAllocationTable(allocation_method="indexed")
        fat.allocate(100, [0, 1])
        # Try to allocate already owned block 1
        assert fat.allocate(101, [1, 2]) is False

    def test_fragmentation_stats(self):
        fat = FileAllocationTable(allocation_method="indexed")
        fat.allocate(100, [0, 1, 3]) # Fragmented since 3 != 1+1
        stats = fat.get_fragmentation_stats()
        assert stats["total_files"] == 1
        assert stats["fragmented_files"] == 1

    def test_validate_allocation(self):
        fat = FileAllocationTable(allocation_method="linked")
        fat.allocate(100, [0, 1, 2])
        assert fat.validate_allocation(100) is True
