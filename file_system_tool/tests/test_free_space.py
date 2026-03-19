"""Tests for the FreeSpaceManager class."""

import pytest
from src.core.free_space import FreeSpaceManager


class TestFreeSpaceManager:
    """Test suite for FreeSpaceManager."""

    def test_initialization(self):
        fsm = FreeSpaceManager(num_blocks=10)
        assert fsm.free_count == 10
        assert fsm.used_count == 0

    def test_allocate_block(self):
        fsm = FreeSpaceManager(num_blocks=10)
        block = fsm.allocate_block()
        assert block is not None
        assert fsm.free_count == 9
        assert fsm.used_count == 1

    def test_allocate_blocks(self):
        fsm = FreeSpaceManager(num_blocks=10)
        blocks = fsm.allocate_blocks(3)
        assert len(blocks) == 3
        assert fsm.free_count == 7

    def test_free_block(self):
        fsm = FreeSpaceManager(num_blocks=10)
        block = fsm.allocate_block()
        fsm.free_block(block)
        assert fsm.free_count == 10

    def test_free_blocks(self):
        fsm = FreeSpaceManager(num_blocks=10)
        blocks = fsm.allocate_blocks(5)
        fsm.free_blocks(blocks)
        assert fsm.free_count == 10

    def test_is_free(self):
        fsm = FreeSpaceManager(num_blocks=10)
        assert fsm.is_free(0) is True
        fsm.allocate_block()
        assert fsm.is_free(0) is False

    def test_full_disk(self):
        fsm = FreeSpaceManager(num_blocks=3)
        fsm.allocate_blocks(3)
        assert fsm.allocate_block() is None

    def test_usage_percent(self):
        fsm = FreeSpaceManager(num_blocks=10)
        fsm.allocate_blocks(5)
        assert fsm.usage_percent == 50.0

    def test_invalid_block_free(self):
        fsm = FreeSpaceManager(num_blocks=10)
        with pytest.raises(IndexError):
            fsm.free_block(10)

    def test_invalid_block_check(self):
        fsm = FreeSpaceManager(num_blocks=10)
        with pytest.raises(IndexError):
            fsm.is_free(-1)
