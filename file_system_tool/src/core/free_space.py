"""
free_space.py - Free space management module.

Provides FreeSpaceManager class that tracks available disk blocks
using a bitmap (bitarray) approach.
"""

from bitarray import bitarray
from ..utils.constants import DEFAULT_NUM_BLOCKS


class FreeSpaceManager:
    """Manages free/used block tracking using a bitmap."""

    def __init__(self, num_blocks=DEFAULT_NUM_BLOCKS):
        """
        Initialize the free space manager.

        Args:
            num_blocks (int): Total number of blocks to manage.
        """
        self.num_blocks = num_blocks
        # 0 = free, 1 = used
        self.bitmap = bitarray(num_blocks)
        self.bitmap.setall(0)

    def allocate_block(self):
        """
        Allocate a single free block.

        Returns:
            int | None: The allocated block number, or None if disk is full.
        """
        try:
            block_num = self.bitmap.index(0)
            self.bitmap[block_num] = 1
            return block_num
        except ValueError:
            return None  # No free blocks

    def allocate_blocks(self, count):
        """
        Allocate multiple contiguous or non-contiguous free blocks.

        Args:
            count (int): Number of blocks to allocate.

        Returns:
            list[int]: List of allocated block numbers (may be fewer than requested).
        """
        allocated = []
        for _ in range(count):
            block = self.allocate_block()
            if block is None:
                break
            allocated.append(block)
        return allocated

    def free_block(self, block_num):
        """
        Free a previously allocated block.

        Args:
            block_num (int): The block number to free.

        Raises:
            IndexError: If block_num is out of range.
        """
        if not (0 <= block_num < self.num_blocks):
            raise IndexError(f"Block number {block_num} out of range [0, {self.num_blocks})")
        self.bitmap[block_num] = 0

    def free_blocks(self, block_nums):
        """
        Free multiple blocks.

        Args:
            block_nums (list[int]): List of block numbers to free.
        """
        for block_num in block_nums:
            self.free_block(block_num)

    def is_free(self, block_num):
        """
        Check if a block is free.

        Args:
            block_num (int): The block number to check.

        Returns:
            bool: True if the block is free.
        """
        if not (0 <= block_num < self.num_blocks):
            raise IndexError(f"Block number {block_num} out of range [0, {self.num_blocks})")
        return self.bitmap[block_num] == 0

    @property
    def free_count(self):
        """Number of free blocks."""
        return self.bitmap.count(0)

    @property
    def used_count(self):
        """Number of used blocks."""
        return self.bitmap.count(1)

    @property
    def usage_percent(self):
        """Disk usage as a percentage."""
        return (self.used_count / self.num_blocks) * 100.0

    def __repr__(self):
        return f"FreeSpaceManager(total={self.num_blocks}, free={self.free_count}, used={self.used_count})"
