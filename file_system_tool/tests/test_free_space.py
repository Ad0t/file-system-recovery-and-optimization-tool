"""Tests for the FreeSpaceManager class."""

import pytest
from src.core.free_space import FreeSpaceManager


class TestFreeSpaceManager:
    """Test suite for FreeSpaceManager."""

    def test_initialization(self):
        fsm = FreeSpaceManager(total_blocks=10)
        assert fsm.get_free_count() == 10
        assert fsm.get_allocated_count() == 0

    def test_allocate_blocks(self):
        fsm = FreeSpaceManager(total_blocks=10)
        blocks = fsm.allocate_blocks(1)
        assert blocks == [0]
        assert fsm.get_free_count() == 9
        assert fsm.get_allocated_count() == 1

    def test_allocate_multiple_blocks(self):
        fsm = FreeSpaceManager(total_blocks=10)
        blocks = fsm.allocate_blocks(3)
        assert len(blocks) == 3
        assert fsm.get_free_count() == 7

    def test_deallocate_blocks(self):
        fsm = FreeSpaceManager(total_blocks=10)
        blocks = fsm.allocate_blocks(3)
        assert fsm.deallocate_blocks(blocks) is True
        assert fsm.get_free_count() == 10

    def test_is_block_free(self):
        fsm = FreeSpaceManager(total_blocks=10)
        assert fsm.is_block_free(0) is True
        fsm.allocate_blocks(1)
        assert fsm.is_block_free(0) is False

    def test_full_disk(self):
        fsm = FreeSpaceManager(total_blocks=3)
        fsm.allocate_blocks(3)
        assert fsm.allocate_blocks(1) is None

    def test_allocation_map(self):
        fsm = FreeSpaceManager(total_blocks=10)
        fsm.allocate_blocks(5)
        stats = fsm.get_allocation_map()
        assert stats["allocated_blocks"] == 5
        assert stats["free_blocks"] == 5

    def test_invalid_block_free(self):
        fsm = FreeSpaceManager(total_blocks=10)
        # deallocate_blocks returns False for out-of-range/already free, no IndexError
        assert fsm.deallocate_blocks([10]) is False
        assert fsm.deallocate_blocks([-1]) is False

    def test_invalid_block_check(self):
        fsm = FreeSpaceManager(total_blocks=10)
        with pytest.raises(IndexError):
            fsm.is_block_free(-1)
