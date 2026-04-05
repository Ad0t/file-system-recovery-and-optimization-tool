"""
file_allocation_table.py - File Allocation Table module.

Provides a FileAllocationTable class that tracks which disk blocks
belong to which files and supports three allocation strategies:
contiguous, linked, and indexed.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Recognised allocation methods
_VALID_METHODS = ("contiguous", "linked", "indexed")


class FileAllocationTable:
    """
    Tracks block-to-file mappings for the simulated file system.

    Supports three allocation strategies:

    - **contiguous**: Blocks must be sequential on disk.
    - **linked**: Each block stores a pointer to the next block in
      the file, forming a singly-linked chain.
    - **indexed**: An index structure maps logical block positions
      to physical block numbers (most flexible).

    Attributes:
        allocation_method (str): Active method — ``'contiguous'``,
            ``'linked'``, or ``'indexed'``.
        file_to_blocks (dict[int, list[int]]): Maps *inode_number*
            to the ordered list of block numbers that hold the file.
        block_to_file (dict[int, int]): Reverse map — *block_number*
            to the *inode_number* that owns it.
        next_pointers (dict[int, int]): For linked allocation only —
            maps each block to the *next* block in the chain.
            The last block maps to ``-1`` (sentinel).
    """

    # Sentinel value for "end of linked chain"
    CHAIN_END = -1

    def __init__(self, allocation_method: str = "indexed"):
        """
        Initialize the file allocation table.

        Args:
            allocation_method (str): One of ``'contiguous'``,
                ``'linked'``, or ``'indexed'``.

        Raises:
            ValueError: If *allocation_method* is unrecognised.
        """
        if allocation_method not in _VALID_METHODS:
            raise ValueError(
                f"Unknown allocation method '{allocation_method}'. "
                f"Choose from {_VALID_METHODS}"
            )

        self.allocation_method: str = allocation_method
        self.file_to_blocks: Dict[int, List[int]] = {}
        self.block_to_file: Dict[int, int] = {}
        self.next_pointers: Dict[int, int] = {}

        logger.info(
            "FileAllocationTable created (method=%s)", allocation_method
        )

    # ------------------------------------------------------------------ #
    #  Strategy-specific allocation
    # ------------------------------------------------------------------ #

    def allocate_contiguous(self, inode_number: int,
                            blocks: List[int]) -> bool:
        """
        Allocate blocks using contiguous strategy.

        All blocks must be sequential (each block = previous + 1).

        Args:
            inode_number (int): File's inode number.
            blocks (list[int]): Ordered block numbers.

        Returns:
            bool: True on success, False if blocks are not contiguous
                or any block is already owned.
        """
        if not blocks:
            return False

        # Validate contiguity
        for i in range(1, len(blocks)):
            if blocks[i] != blocks[i - 1] + 1:
                logger.warning(
                    "allocate_contiguous: blocks are not sequential "
                    "(gap at index %d: %d -> %d)",
                    i, blocks[i - 1], blocks[i],
                )
                return False

        # Check no block is already owned
        for b in blocks:
            if b in self.block_to_file:
                logger.warning(
                    "allocate_contiguous: block %d already owned by inode %d",
                    b, self.block_to_file[b],
                )
                return False

        self.file_to_blocks[inode_number] = list(blocks)
        for b in blocks:
            self.block_to_file[b] = inode_number

        logger.debug(
            "Contiguous alloc: inode %d -> blocks %d–%d",
            inode_number, blocks[0], blocks[-1],
        )
        return True

    def allocate_linked(self, inode_number: int,
                        blocks: List[int]) -> bool:
        """
        Allocate blocks using linked strategy.

        Creates a next-pointer chain:
        ``blocks[0] → blocks[1] → … → blocks[-1] → CHAIN_END``.

        Args:
            inode_number (int): File's inode number.
            blocks (list[int]): Ordered block numbers.

        Returns:
            bool: True on success.
        """
        if not blocks:
            return False

        # Check no block is already owned
        for b in blocks:
            if b in self.block_to_file:
                logger.warning(
                    "allocate_linked: block %d already owned by inode %d",
                    b, self.block_to_file[b],
                )
                return False

        self.file_to_blocks[inode_number] = list(blocks)
        for b in blocks:
            self.block_to_file[b] = inode_number

        # Build the linked chain
        for i in range(len(blocks) - 1):
            self.next_pointers[blocks[i]] = blocks[i + 1]
        self.next_pointers[blocks[-1]] = self.CHAIN_END

        logger.debug(
            "Linked alloc: inode %d -> %d blocks (chain %d→…→%d)",
            inode_number, len(blocks), blocks[0], blocks[-1],
        )
        return True

    def allocate_indexed(self, inode_number: int,
                         blocks: List[int]) -> bool:
        """
        Allocate blocks using indexed strategy.

        Blocks are stored as a flat list; no contiguity requirement
        and no linked-chain overhead.

        Args:
            inode_number (int): File's inode number.
            blocks (list[int]): Ordered block numbers.

        Returns:
            bool: True on success.
        """
        if not blocks:
            return False

        # Check no block is already owned
        for b in blocks:
            if b in self.block_to_file:
                logger.warning(
                    "allocate_indexed: block %d already owned by inode %d",
                    b, self.block_to_file[b],
                )
                return False

        self.file_to_blocks[inode_number] = list(blocks)
        for b in blocks:
            self.block_to_file[b] = inode_number

        logger.debug(
            "Indexed alloc: inode %d -> %d blocks", inode_number, len(blocks),
        )
        return True

    # ------------------------------------------------------------------ #
    #  Unified allocation dispatcher
    # ------------------------------------------------------------------ #

    def allocate(self, inode_number: int, blocks: List[int]) -> bool:
        """
        Allocate blocks using the active allocation method.

        Convenience wrapper that dispatches to the strategy-specific
        method.

        Args:
            inode_number (int): File's inode number.
            blocks (list[int]): Ordered block numbers.

        Returns:
            bool: True on success.
        """
        dispatch = {
            "contiguous": self.allocate_contiguous,
            "linked": self.allocate_linked,
            "indexed": self.allocate_indexed,
        }
        return dispatch[self.allocation_method](inode_number, blocks)

    # ------------------------------------------------------------------ #
    #  Deallocation
    # ------------------------------------------------------------------ #

    def deallocate(self, inode_number: int) -> List[int]:
        """
        Remove all block mappings for the given file.

        Clears entries from ``file_to_blocks``, ``block_to_file``,
        and ``next_pointers`` (if linked).

        Args:
            inode_number (int): File's inode number.

        Returns:
            list[int]: The block numbers that were freed
                (empty if inode was not found).
        """
        blocks = self.file_to_blocks.pop(inode_number, [])
        if not blocks:
            return []

        for b in blocks:
            self.block_to_file.pop(b, None)
            self.next_pointers.pop(b, None)  # safe even if not linked

        logger.debug(
            "Deallocated inode %d: freed %d blocks", inode_number, len(blocks),
        )
        return blocks

    # ------------------------------------------------------------------ #
    #  Queries
    # ------------------------------------------------------------------ #

    def get_file_blocks(self, inode_number: int) -> List[int]:
        """
        Return the list of blocks allocated to a file.

        Args:
            inode_number (int): File's inode number.

        Returns:
            list[int]: Block numbers (empty if file not found).
        """
        return list(self.file_to_blocks.get(inode_number, []))

    def get_block_owner(self, block_number: int) -> Optional[int]:
        """
        Return the inode number that owns a block.

        Args:
            block_number (int): Disk block number.

        Returns:
            int | None: Owning inode number, or None if the block
                is free.
        """
        return self.block_to_file.get(block_number)

    # ------------------------------------------------------------------ #
    #  Linked-chain traversal
    # ------------------------------------------------------------------ #

    def follow_linked_chain(self, start_block: int) -> List[int]:
        """
        Follow the next-pointer chain from *start_block*.

        Only meaningful when the allocation method is ``'linked'``.

        Args:
            start_block (int): First block of the chain.

        Returns:
            list[int]: Ordered list of blocks in the chain.
                Empty if this is not linked allocation or the block
                is not in ``next_pointers``.
        """
        if self.allocation_method != "linked":
            return []

        chain: List[int] = []
        visited: set = set()
        current = start_block

        while current != self.CHAIN_END and current not in visited:
            if current not in self.next_pointers and current != start_block:
                break
            visited.add(current)
            chain.append(current)
            current = self.next_pointers.get(current, self.CHAIN_END)

        return chain

    # ------------------------------------------------------------------ #
    #  Fragmentation analysis
    # ------------------------------------------------------------------ #

    def is_fragmented(self, inode_number: int) -> bool:
        """
        Check whether a file's blocks are fragmented.

        - **contiguous / indexed**: fragmented if blocks are not
          strictly sequential (each = previous + 1).
        - **linked**: always considered fragmented because the
          on-disk layout is inherently non-sequential.

        Args:
            inode_number (int): File's inode number.

        Returns:
            bool: True if fragmented (or if file not found).
        """
        blocks = self.file_to_blocks.get(inode_number)
        if not blocks:
            return False

        if self.allocation_method == "linked":
            return True  # linked allocation is inherently fragmented

        # For contiguous and indexed: sequential = not fragmented
        for i in range(1, len(blocks)):
            if blocks[i] != blocks[i - 1] + 1:
                return True
        return False

    def get_fragmentation_stats(self) -> Dict:
        """
        Calculate overall fragmentation across all tracked files.

        Returns:
            dict: Statistics containing:
                - total_files (int)
                - fragmented_files (int)
                - fragmentation_percentage (float)
                - avg_gaps_per_file (float): Average number of
                  non-sequential transitions per file.
        """
        total = len(self.file_to_blocks)
        if total == 0:
            return {
                "total_files": 0,
                "fragmented_files": 0,
                "fragmentation_percentage": 0.0,
                "avg_gaps_per_file": 0.0,
            }

        fragmented = 0
        total_gaps = 0

        for inode_number, blocks in self.file_to_blocks.items():
            if not blocks or len(blocks) <= 1:
                continue

            file_gaps = 0
            for i in range(1, len(blocks)):
                if blocks[i] != blocks[i - 1] + 1:
                    file_gaps += 1

            if self.allocation_method == "linked":
                # Linked is always fragmented
                fragmented += 1
                file_gaps = max(file_gaps, 1)
            elif file_gaps > 0:
                fragmented += 1

            total_gaps += file_gaps

        return {
            "total_files": total,
            "fragmented_files": fragmented,
            "fragmentation_percentage": (fragmented / total) * 100.0,
            "avg_gaps_per_file": total_gaps / total,
        }

    # ------------------------------------------------------------------ #
    #  Validation
    # ------------------------------------------------------------------ #

    def validate_allocation(self, inode_number: int) -> bool:
        """
        Verify the integrity of a file's block allocation.

        Checks:
          1. Every block in ``file_to_blocks[inode]`` is also present
             in ``block_to_file`` and points back to the same inode.
          2. For linked allocation, the ``next_pointers`` chain is
             complete and covers all blocks.

        Args:
            inode_number (int): File's inode number.

        Returns:
            bool: True if the allocation is consistent.
        """
        blocks = self.file_to_blocks.get(inode_number)
        if blocks is None:
            logger.warning(
                "validate: inode %d not found in file_to_blocks",
                inode_number,
            )
            return False

        # Check 1: block_to_file consistency
        for b in blocks:
            owner = self.block_to_file.get(b)
            if owner != inode_number:
                logger.warning(
                    "validate: block %d should belong to inode %d "
                    "but block_to_file says %s",
                    b, inode_number, owner,
                )
                return False

        # Check 2: linked-chain completeness
        if self.allocation_method == "linked" and len(blocks) > 0:
            chain = self.follow_linked_chain(blocks[0])
            if chain != blocks:
                logger.warning(
                    "validate: linked chain mismatch for inode %d. "
                    "Expected %s, got %s",
                    inode_number, blocks, chain,
                )
                return False

        return True

    # ------------------------------------------------------------------ #
    #  Dunder
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"FileAllocationTable(method='{self.allocation_method}', "
            f"files={len(self.file_to_blocks)}, "
            f"blocks_used={len(self.block_to_file)})"
        )
