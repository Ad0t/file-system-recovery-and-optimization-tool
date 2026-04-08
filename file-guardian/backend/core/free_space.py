"""
free_space.py - Free space management module.

Provides a FreeSpaceManager class that tracks available disk blocks
using a bitmap (bitarray) approach. Supports contiguous and scattered
allocation with first-fit, best-fit, and worst-fit strategies.

Dependencies:
    - bitarray: Efficient bit-level bitmap for block tracking.
    - FileSystemConfig: Default block count from constants.

Usage::

    from src.core.free_space import FreeSpaceManager

    fsm = FreeSpaceManager(total_blocks=1000, strategy='first_fit')
    blocks = fsm.allocate_blocks(10, contiguous=True)  # [0..9]
    fsm.deallocate_blocks(blocks)                      # free them
    print(fsm.get_allocation_map())                    # stats dict
"""

import logging
from typing import Dict, List, Optional

from bitarray import bitarray

from utils.constants import FileSystemConfig

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

        When *contiguous* is True the active strategy (first_fit,
        best_fit or worst_fit) is used to locate a suitable run of
        consecutive free blocks.  When False, ``_scattered_fit`` is
        called instead, collecting any available free blocks.

        Args:
            num_blocks (int): How many blocks to allocate (must be > 0).
            contiguous (bool): If True, all allocated blocks will be
                consecutive on disk. If False, blocks may be scattered.

        Returns:
            list[int] | None: Ordered list of allocated block numbers,
                or None if the request cannot be satisfied.

        Raises:
            ValueError: If num_blocks is not positive.

        Example::

            >>> fsm = FreeSpaceManager(total_blocks=100)
            >>> fsm.allocate_blocks(5, contiguous=True)
            [0, 1, 2, 3, 4]
            >>> fsm.allocate_blocks(3, contiguous=False)
            [5, 6, 7]

        Note:
            Allocation marks blocks as used in the internal bitmap.
            Call ``deallocate_blocks()`` to free them later.
        """
        if num_blocks <= 0:
            raise ValueError(
                f"num_blocks must be positive, got {num_blocks}"
            )

        if not contiguous:
            return self._scattered_fit(num_blocks)

        # Dispatch to the strategy-specific contiguous allocator
        strategy_map = {
            "first_fit": self._first_fit_contiguous,
            "best_fit":  self._best_fit_contiguous,
            "worst_fit": self._worst_fit_contiguous,
        }
        allocator = strategy_map[self.allocation_strategy]
        return allocator(num_blocks)

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
    #  Contiguous space search (delegates to active strategy)
    # ------------------------------------------------------------------ #

    def find_contiguous_space(self, num_blocks: int) -> Optional[int]:
        """
        Find a starting block index for *num_blocks* contiguous free blocks.

        Delegates to the active allocation strategy. This is a **search-only**
        method — the bitmap is *not* modified.

        Args:
            num_blocks (int): Number of consecutive free blocks needed.

        Returns:
            int | None: Starting block number, or None if no suitable
                contiguous space exists.
        """
        if num_blocks <= 0 or num_blocks > self.total_blocks:
            return None

        holes = self.get_all_free_regions()

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
    #  Strategy management
    # ------------------------------------------------------------------ #

    def set_allocation_strategy(self, strategy: str) -> bool:
        """
        Change the allocation strategy at runtime.

        Args:
            strategy (str): One of 'first_fit', 'best_fit', or 'worst_fit'.

        Returns:
            bool: True if the strategy was set successfully,
                False if the value is invalid.
        """
        if strategy not in _VALID_STRATEGIES:
            logger.warning(
                "set_allocation_strategy: invalid strategy '%s'. "
                "Choose from %s", strategy, _VALID_STRATEGIES,
            )
            return False

        self.allocation_strategy = strategy
        logger.info("Allocation strategy changed to '%s'", strategy)
        return True

    # ------------------------------------------------------------------ #
    #  Free-region analysis
    # ------------------------------------------------------------------ #

    def get_all_free_regions(self) -> List[tuple]:
        """
        Return every contiguous run of free blocks on the disk.

        Useful for analysis, visualisation, and strategy selection.

        Returns:
            list[tuple[int, int]]: Each element is
                ``(start_block, length)`` where *start_block* is the
                first free block in the run and *length* is the number
                of consecutive free blocks.
        """
        regions: List[tuple] = []
        i = 0
        while i < self.total_blocks:
            if self.bitmap[i] == 0:
                start = i
                while i < self.total_blocks and self.bitmap[i] == 0:
                    i += 1
                regions.append((start, i - start))
            else:
                i += 1
        return regions

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
        regions = self.get_all_free_regions()
        largest = max((length for _, length in regions), default=0)

        return {
            "total_blocks": self.total_blocks,
            "free_blocks": self.get_free_count(),
            "allocated_blocks": self.get_allocated_count(),
            "fragmentation_percentage": self.get_fragmentation_percentage(),
            "largest_contiguous_space": largest,
        }

    # ------------------------------------------------------------------ #
    #  Strategy implementations (contiguous)
    # ------------------------------------------------------------------ #

    def _first_fit_contiguous(self, num_blocks: int) -> Optional[List[int]]:
        """
        First-fit contiguous allocation.

        Scans the bitmap from block 0 and returns the first contiguous
        free region that is large enough to satisfy the request.
        This is the fastest strategy but can cause fragmentation at
        the start of the disk over time.

        Args:
            num_blocks (int): Number of contiguous blocks to allocate.

        Returns:
            list[int] | None: Allocated block numbers, or None.
        """
        regions = self.get_all_free_regions()
        for start, length in regions:
            if length >= num_blocks:
                block_list = list(range(start, start + num_blocks))
                for b in block_list:
                    self.bitmap[b] = 1
                logger.debug(
                    "first_fit: allocated %d blocks at %d",
                    num_blocks, start,
                )
                return block_list

        logger.warning(
            "first_fit: cannot allocate %d contiguous blocks", num_blocks
        )
        return None

    def _best_fit_contiguous(self, num_blocks: int) -> Optional[List[int]]:
        """
        Best-fit contiguous allocation.

        Scans the *entire* bitmap to find all free regions, then picks
        the one whose size is closest to (but >= ) *num_blocks*.
        Minimises wasted space in the chosen hole, but may create many
        tiny unusable fragments over time.

        Args:
            num_blocks (int): Number of contiguous blocks to allocate.

        Returns:
            list[int] | None: Allocated block numbers, or None.
        """
        regions = self.get_all_free_regions()
        best = None  # (start, length)

        for start, length in regions:
            if length >= num_blocks:
                if best is None or length < best[1]:
                    best = (start, length)

        if best is None:
            logger.warning(
                "best_fit: cannot allocate %d contiguous blocks", num_blocks
            )
            return None

        block_list = list(range(best[0], best[0] + num_blocks))
        for b in block_list:
            self.bitmap[b] = 1
        logger.debug(
            "best_fit: allocated %d blocks at %d (hole size %d)",
            num_blocks, best[0], best[1],
        )
        return block_list

    def _worst_fit_contiguous(self, num_blocks: int) -> Optional[List[int]]:
        """
        Worst-fit contiguous allocation.

        Scans the entire bitmap to find the *largest* free region and
        allocates from the start of that region. This maximises the
        remaining contiguous space after the allocation, which can
        help reduce future fragmentation for large requests.

        Args:
            num_blocks (int): Number of contiguous blocks to allocate.

        Returns:
            list[int] | None: Allocated block numbers, or None.
        """
        regions = self.get_all_free_regions()
        worst = None  # (start, length)

        for start, length in regions:
            if length >= num_blocks:
                if worst is None or length > worst[1]:
                    worst = (start, length)

        if worst is None:
            logger.warning(
                "worst_fit: cannot allocate %d contiguous blocks", num_blocks
            )
            return None

        block_list = list(range(worst[0], worst[0] + num_blocks))
        for b in block_list:
            self.bitmap[b] = 1
        logger.debug(
            "worst_fit: allocated %d blocks at %d (hole size %d)",
            num_blocks, worst[0], worst[1],
        )
        return block_list

    # ------------------------------------------------------------------ #
    #  Scattered (non-contiguous) allocation
    # ------------------------------------------------------------------ #

    def _scattered_fit(self, num_blocks: int) -> Optional[List[int]]:
        """
        Scattered (non-contiguous) allocation.

        Collects any *num_blocks* free blocks by scanning from block 0.
        The returned blocks are not guaranteed to be consecutive.

        Args:
            num_blocks (int): Number of blocks to allocate.

        Returns:
            list[int] | None: Allocated block numbers, or None if
                fewer than *num_blocks* are available.
        """
        if self.get_free_count() < num_blocks:
            logger.warning(
                "scattered_fit: cannot allocate %d blocks — only %d free",
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

        logger.debug(
            "scattered_fit: allocated %d blocks: %s", num_blocks, allocated
        )
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
