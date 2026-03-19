"""
free_space.py - Free space management module.

Provides a FreeSpaceManager class that tracks available disk blocks
using a bitmap (bitarray) approach. Supports contiguous and scattered
allocation with first-fit, best-fit, and worst-fit strategies.
"""

import logging
from typing import Dict, List, Optional

from bitarray import bitarray

from ..utils.constants import FileSystemConfig

logger = logging.getLogger(__name__)

# Valid allocation strategy names
_VALID_STRATEGIES = ("first_fit", "best_fit", "worst_fit")


class FreeSpaceManager:
    """
    Manages free/used block tracking using a bitmap.

    Each bit in the bitmap corresponds to one disk block:
      - 0 → free (available for allocation)
      - 1 → allocated (in use)

    The manager supports three allocation strategies:
      - **first_fit**: Scan from the beginning; pick the first hole
        that is large enough.  Fastest, but can cause fragmentation
        at the start of the disk.
      - **best_fit**: Pick the smallest hole that is large enough.
        Minimises wasted space inside the hole but can create many
        tiny unusable fragments.
      - **worst_fit**: Pick the largest hole available. Leaves the
        largest possible remainder, which may be useful for future
        large allocations.

    Attributes:
        total_blocks (int): Total number of blocks managed.
        bitmap (bitarray): Bit vector — 0 = free, 1 = allocated.
        allocation_strategy (str): One of 'first_fit', 'best_fit',
            or 'worst_fit'.
    """

    def __init__(self, total_blocks: int = FileSystemConfig.SMALL_DISK,
                 strategy: str = "first_fit"):
        """
        Initialize the free space manager.

        Args:
            total_blocks (int): Total number of blocks to manage.
                Must be positive.
            strategy (str): Allocation strategy — one of
                'first_fit', 'best_fit', or 'worst_fit'.

        Raises:
            ValueError: If total_blocks is not positive or strategy
                is unrecognised.
        """
        if total_blocks <= 0:
            raise ValueError(
                f"total_blocks must be positive, got {total_blocks}"
            )
        if strategy not in _VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Choose from {_VALID_STRATEGIES}"
            )

        self.total_blocks = total_blocks
        self.allocation_strategy = strategy

        # 0 = free, 1 = allocated — all blocks start free
        self.bitmap = bitarray(total_blocks)
        self.bitmap.setall(0)

        logger.info(
            "FreeSpaceManager initialized: %d blocks, strategy=%s",
            total_blocks, strategy,
        )

    # ------------------------------------------------------------------ #
    #  Core allocation / deallocation
    # ------------------------------------------------------------------ #

    def allocate_blocks(self, num_blocks: int,
                        contiguous: bool = True) -> Optional[List[int]]:
        """
        Allocate the requested number of blocks.

        Args:
            num_blocks (int): How many blocks to allocate (must be > 0).
            contiguous (bool): If True, all allocated blocks will be
                consecutive on disk. If False, blocks may be scattered.

        Returns:
            list[int] | None: Ordered list of allocated block numbers,
                or None if the request cannot be satisfied.

        Raises:
            ValueError: If num_blocks is not positive.
        """
        if num_blocks <= 0:
            raise ValueError(
                f"num_blocks must be positive, got {num_blocks}"
            )

        if contiguous:
            return self._allocate_contiguous(num_blocks)
        return self._allocate_scattered(num_blocks)

    def deallocate_blocks(self, block_list: List[int]) -> bool:
        """
        Free the specified blocks.

        Every block in the list must be currently allocated (bit == 1).
        If any block is out of range or already free, the method logs
        a warning and returns False without modifying the bitmap.

        Args:
            block_list (list[int]): Block numbers to free.

        Returns:
            bool: True if all blocks were successfully freed.
        """
        # --- pre-validation pass (all-or-nothing) ---
        for block_num in block_list:
            if not (0 <= block_num < self.total_blocks):
                logger.warning(
                    "deallocate_blocks: block %d out of range [0, %d)",
                    block_num, self.total_blocks,
                )
                return False
            if self.bitmap[block_num] == 0:
                logger.warning(
                    "deallocate_blocks: block %d is already free", block_num
                )
                return False

        # --- all checks passed — perform deallocation ---
        for block_num in block_list:
            self.bitmap[block_num] = 0

        logger.debug("Deallocated %d blocks: %s", len(block_list), block_list)
        return True

    # ------------------------------------------------------------------ #
    #  Queries
    # ------------------------------------------------------------------ #

    def is_block_free(self, block_num: int) -> bool:
        """
        Check whether a specific block is free.

        Args:
            block_num (int): Zero-based block index.

        Returns:
            bool: True if the block is free (bit == 0).

        Raises:
            IndexError: If block_num is out of range.
        """
        if not (0 <= block_num < self.total_blocks):
            raise IndexError(
                f"Block number {block_num} out of range "
                f"[0, {self.total_blocks})"
            )
        return self.bitmap[block_num] == 0

    def get_free_count(self) -> int:
        """
        Return the total number of free (unallocated) blocks.

        Returns:
            int: Count of bits set to 0.
        """
        return self.bitmap.count(0)

    def get_allocated_count(self) -> int:
        """
        Return the total number of allocated blocks.

        Returns:
            int: Count of bits set to 1.
        """
        return self.bitmap.count(1)

    # ------------------------------------------------------------------ #
    #  Fragmentation analysis
    # ------------------------------------------------------------------ #

    def get_fragmentation_percentage(self) -> float:
        """
        Calculate the fragmentation level of the disk.

        Fragmentation is measured by counting the number of transitions
        between free (0) and allocated (1) regions across the bitmap.
        More transitions indicate a more fragmented layout.

        Formula::

            fragmentation = (transitions / total_blocks) * 100

        Returns:
            float: Fragmentation as a percentage (0.0 – 100.0).
                0 % means all free space is in one contiguous chunk.
        """
        if self.total_blocks <= 1:
            return 0.0

        transitions = 0
        for i in range(1, self.total_blocks):
            if self.bitmap[i] != self.bitmap[i - 1]:
                transitions += 1

        return (transitions / self.total_blocks) * 100.0

    # ------------------------------------------------------------------ #
    #  Contiguous space search
    # ------------------------------------------------------------------ #

    def find_contiguous_space(self, num_blocks: int) -> Optional[int]:
        """
        Find a starting block index for *num_blocks* contiguous free blocks.

        The search strategy is determined by ``self.allocation_strategy``:

        - **first_fit** — returns the start of the first hole that is
          large enough.
        - **best_fit** — returns the start of the smallest hole that
          fits the request.
        - **worst_fit** — returns the start of the largest free hole.

        Args:
            num_blocks (int): Number of consecutive free blocks needed.

        Returns:
            int | None: Starting block number, or None if no suitable
                contiguous space exists.
        """
        if num_blocks <= 0 or num_blocks > self.total_blocks:
            return None

        # Collect every free hole as (start, length)
        holes = self._find_free_holes()

        if self.allocation_strategy == "first_fit":
            for start, length in holes:
                if length >= num_blocks:
                    return start
            return None

        elif self.allocation_strategy == "best_fit":
            best = None
            for start, length in holes:
                if length >= num_blocks:
                    if best is None or length < best[1]:
                        best = (start, length)
            return best[0] if best else None

        else:  # worst_fit
            worst = None
            for start, length in holes:
                if length >= num_blocks:
                    if worst is None or length > worst[1]:
                        worst = (start, length)
            return worst[0] if worst else None

    # ------------------------------------------------------------------ #
    #  Allocation map / statistics
    # ------------------------------------------------------------------ #

    def get_allocation_map(self) -> Dict:
        """
        Return a summary of allocation statistics.

        Returns:
            dict: A dictionary containing:
                - total_blocks (int)
                - free_blocks (int)
                - allocated_blocks (int)
                - fragmentation_percentage (float)
                - largest_contiguous_space (int)
        """
        # Find the largest contiguous free hole
        holes = self._find_free_holes()
        largest = max((length for _, length in holes), default=0)

        return {
            "total_blocks": self.total_blocks,
            "free_blocks": self.get_free_count(),
            "allocated_blocks": self.get_allocated_count(),
            "fragmentation_percentage": self.get_fragmentation_percentage(),
            "largest_contiguous_space": largest,
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _find_free_holes(self) -> List[tuple]:
        """
        Scan the bitmap and return every contiguous run of free blocks.

        Returns:
            list[tuple[int, int]]: Each element is (start_index, length).
        """
        holes: List[tuple] = []
        i = 0
        while i < self.total_blocks:
            if self.bitmap[i] == 0:
                start = i
                while i < self.total_blocks and self.bitmap[i] == 0:
                    i += 1
                holes.append((start, i - start))
            else:
                i += 1
        return holes

    def _allocate_contiguous(self, num_blocks: int) -> Optional[List[int]]:
        """
        Internal: allocate a contiguous run of blocks using the
        configured strategy.
        """
        start = self.find_contiguous_space(num_blocks)
        if start is None:
            logger.warning(
                "Cannot allocate %d contiguous blocks (strategy=%s)",
                num_blocks, self.allocation_strategy,
            )
            return None

        block_list = list(range(start, start + num_blocks))
        for b in block_list:
            self.bitmap[b] = 1

        logger.debug(
            "Allocated %d contiguous blocks starting at %d", num_blocks, start
        )
        return block_list

    def _allocate_scattered(self, num_blocks: int) -> Optional[List[int]]:
        """
        Internal: allocate blocks from anywhere on disk (non-contiguous).

        Scans from the beginning and picks the first *num_blocks* free
        blocks found.
        """
        if self.get_free_count() < num_blocks:
            logger.warning(
                "Cannot allocate %d scattered blocks — only %d free",
                num_blocks, self.get_free_count(),
            )
            return None

        allocated: List[int] = []
        for i in range(self.total_blocks):
            if self.bitmap[i] == 0:
                self.bitmap[i] = 1
                allocated.append(i)
                if len(allocated) == num_blocks:
                    break

        logger.debug("Allocated %d scattered blocks: %s", num_blocks, allocated)
        return allocated

    # ------------------------------------------------------------------ #
    #  Dunder helpers
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"FreeSpaceManager(total={self.total_blocks}, "
            f"free={self.get_free_count()}, "
            f"allocated={self.get_allocated_count()}, "
            f"strategy='{self.allocation_strategy}')"
        )
