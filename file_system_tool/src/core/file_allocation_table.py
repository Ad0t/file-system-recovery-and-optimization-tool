"""
file_allocation_table.py - FAT (File Allocation Table) module.

Provides a FileAllocationTable class that tracks block chains
for files using a FAT-style linked allocation scheme.
"""

from ..utils.constants import DEFAULT_NUM_BLOCKS, FAT_FREE, FAT_EOF, FAT_BAD


class FileAllocationTable:
    """Implements a FAT-style block chain tracker."""

    def __init__(self, num_blocks=DEFAULT_NUM_BLOCKS):
        """
        Initialize the File Allocation Table.

        Args:
            num_blocks (int): Total number of blocks.
        """
        self.num_blocks = num_blocks
        # Each entry points to the next block in the chain, or a special value
        self.table = [FAT_FREE] * num_blocks

    def allocate_chain(self, block_list):
        """
        Create a chain of blocks in the FAT.

        Args:
            block_list (list[int]): Ordered list of block numbers forming a file.
        """
        if not block_list:
            return
        for i in range(len(block_list) - 1):
            self.table[block_list[i]] = block_list[i + 1]
        self.table[block_list[-1]] = FAT_EOF

    def get_chain(self, start_block):
        """
        Follow a chain from a starting block.

        Args:
            start_block (int): The first block in the chain.

        Returns:
            list[int]: List of block numbers in the chain.
        """
        chain = []
        current = start_block
        visited = set()
        while current not in (FAT_FREE, FAT_EOF, FAT_BAD) and current not in visited:
            if not (0 <= current < self.num_blocks):
                break
            visited.add(current)
            chain.append(current)
            current = self.table[current]
        return chain

    def free_chain(self, start_block):
        """
        Free an entire chain starting from a block.

        Args:
            start_block (int): The first block of the chain to free.

        Returns:
            list[int]: List of freed block numbers.
        """
        chain = self.get_chain(start_block)
        for block in chain:
            self.table[block] = FAT_FREE
        return chain

    def mark_bad(self, block_num):
        """
        Mark a block as bad/unusable.

        Args:
            block_num (int): The block to mark as bad.
        """
        if 0 <= block_num < self.num_blocks:
            self.table[block_num] = FAT_BAD

    def is_free(self, block_num):
        """Check if a block is free in the FAT."""
        return self.table[block_num] == FAT_FREE

    def is_eof(self, block_num):
        """Check if a block is the end of a chain."""
        return self.table[block_num] == FAT_EOF

    def is_bad(self, block_num):
        """Check if a block is marked as bad."""
        return self.table[block_num] == FAT_BAD

    @property
    def free_count(self):
        """Number of free blocks in the FAT."""
        return self.table.count(FAT_FREE)

    def __repr__(self):
        return f"FileAllocationTable(blocks={self.num_blocks}, free={self.free_count})"
