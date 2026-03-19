"""
disk.py - Simulated disk storage module.

Provides a Disk class that simulates a block-based storage device
with configurable block size and total number of blocks.
"""

import numpy as np
from ..utils.constants import DEFAULT_BLOCK_SIZE, DEFAULT_NUM_BLOCKS


class Disk:
    """Simulates a block-based disk storage device."""

    def __init__(self, num_blocks=DEFAULT_NUM_BLOCKS, block_size=DEFAULT_BLOCK_SIZE):
        """
        Initialize the simulated disk.

        Args:
            num_blocks (int): Total number of blocks on the disk.
            block_size (int): Size of each block in bytes.
        """
        self.num_blocks = num_blocks
        self.block_size = block_size
        # Each block is a bytearray of block_size bytes, initialized to zero
        self.blocks = [bytearray(block_size) for _ in range(num_blocks)]

    def read_block(self, block_num):
        """
        Read data from a specific block.

        Args:
            block_num (int): The block number to read.

        Returns:
            bytearray: A copy of the block's data.

        Raises:
            IndexError: If block_num is out of range.
        """
        if not (0 <= block_num < self.num_blocks):
            raise IndexError(f"Block number {block_num} out of range [0, {self.num_blocks})")
        return bytearray(self.blocks[block_num])

    def write_block(self, block_num, data):
        """
        Write data to a specific block.

        Args:
            block_num (int): The block number to write to.
            data (bytes | bytearray): The data to write (will be truncated/padded to block_size).

        Raises:
            IndexError: If block_num is out of range.
        """
        if not (0 <= block_num < self.num_blocks):
            raise IndexError(f"Block number {block_num} out of range [0, {self.num_blocks})")
        block = bytearray(self.block_size)
        block[:len(data)] = data[:self.block_size]
        self.blocks[block_num] = block

    def clear_block(self, block_num):
        """
        Clear (zero out) a specific block.

        Args:
            block_num (int): The block number to clear.
        """
        if not (0 <= block_num < self.num_blocks):
            raise IndexError(f"Block number {block_num} out of range [0, {self.num_blocks})")
        self.blocks[block_num] = bytearray(self.block_size)

    def get_disk_usage(self):
        """
        Calculate the percentage of non-empty blocks.

        Returns:
            float: Disk usage as a percentage (0.0 - 100.0).
        """
        used = sum(1 for block in self.blocks if any(block))
        return (used / self.num_blocks) * 100.0

    def __repr__(self):
        return f"Disk(num_blocks={self.num_blocks}, block_size={self.block_size})"
