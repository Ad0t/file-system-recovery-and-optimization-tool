"""
disk.py - Simulated disk storage module.

Provides a Disk class that simulates a block-based storage device
with configurable block size, total blocks, and I/O tracking metadata.
Supports single and batch I/O, persistence via pickle, and per-block
status inspection.

Dependencies:
    - pickle (stdlib): Disk state serialization.
    - os (stdlib): Directory creation for persistence.
    - FileSystemConfig: Default block/disk sizes from constants.

Usage::

    from src.core.disk import Disk

    disk = Disk(total_blocks=1024, block_size=4096)
    disk.write_block(0, b"hello")
    data = disk.read_block(0)      # b"hello"
    disk.save_to_file("data/disk.img")
"""

import logging
import os
import pickle
import time
from typing import Dict, List, Optional

from ..utils.constants import FileSystemConfig

logger = logging.getLogger(__name__)


class Disk:
    """
    Simulates a block-based disk storage device.

    Each block is either None (empty/unallocated) or contains a bytes
    object of at most block_size bytes. The disk tracks read/write
    statistics via its metadata dictionary and per-block access times
    via block_access_times.

    Attributes:
        total_blocks (int): Total number of blocks on the disk.
        block_size (int): Size of each block in bytes.
        blocks (list): Block storage — None for empty, bytes for occupied.
        metadata (dict): Disk-level statistics and timestamps.
        block_access_times (dict): Maps block_num → last-access timestamp.
    """

    def __init__(self, total_blocks: int = FileSystemConfig.SMALL_DISK,
                 block_size: int = FileSystemConfig.DEFAULT_BLOCK_SIZE):
        """
        Initialize the simulated disk.

        Args:
            total_blocks (int): Total number of blocks on the disk.
                Must be a positive integer. Defaults to SMALL_DISK (1024).
            block_size (int): Size of each block in bytes.
                Must be a positive integer. Defaults to 4096 (4 KB).

        Raises:
            ValueError: If total_blocks or block_size is not positive.
        """
        if total_blocks <= 0:
            raise ValueError(f"total_blocks must be positive, got {total_blocks}")
        if block_size <= 0:
            raise ValueError(f"block_size must be positive, got {block_size}")

        self.total_blocks = total_blocks
        self.block_size = block_size

        # None indicates an empty / unallocated block
        self.blocks: List[Optional[bytes]] = [None] * total_blocks

        # Per-block access timestamps (block_num → float)
        self.block_access_times: Dict[int, float] = {}

        # Disk-level metadata for statistics and diagnostics
        self.metadata = {
            "creation_time": time.time(),
            "total_writes": 0,
            "total_reads": 0,
        }

        logger.info("Disk initialized: %d blocks × %d B", total_blocks, block_size)

    # --------------------------------------------------------------------- #
    #  Core I/O (single block)
    # --------------------------------------------------------------------- #

    def read_block(self, block_num: int) -> Optional[bytes]:
        """
        Read data from a specific block.

        Args:
            block_num (int): Zero-based index of the block to read.

        Returns:
            bytes | None: The data stored in the block, or None if the
                block is empty (has never been written to).

        Raises:
            IndexError: If block_num is outside [0, total_blocks).

        Example::

            >>> disk = Disk(total_blocks=10)
            >>> disk.write_block(0, b"hello")
            True
            >>> disk.read_block(0)
            b'hello'
            >>> disk.read_block(1) is None  # empty block
            True
        """
        if not (0 <= block_num < self.total_blocks):
            raise IndexError(
                f"Block number {block_num} out of range [0, {self.total_blocks})"
            )

        self.metadata["total_reads"] += 1
        self.block_access_times[block_num] = time.time()
        return self.blocks[block_num]

    def write_block(self, block_num: int, data: bytes) -> bool:
        """
        Write data to a specific block.

        The supplied data must not exceed block_size bytes. Data shorter
        than block_size is stored as-is (no padding).

        Args:
            block_num (int): Zero-based index of the block to write to.
            data (bytes | bytearray): The data to write.

        Returns:
            bool: True on successful write.

        Raises:
            IndexError: If block_num is outside [0, total_blocks).
            TypeError:  If data is not bytes or bytearray.
            ValueError: If data length exceeds block_size.

        Example::

            >>> disk = Disk(total_blocks=10)
            >>> disk.write_block(0, b"block data")
            True
            >>> disk.write_block(0, b"x" * 5000)  # too large
            ValueError: Data size (5000 bytes) exceeds block size (4096 bytes)
        """
        if not (0 <= block_num < self.total_blocks):
            raise IndexError(
                f"Block number {block_num} out of range [0, {self.total_blocks})"
            )
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(
                f"data must be bytes or bytearray, got {type(data).__name__}"
            )
        if len(data) > self.block_size:
            raise ValueError(
                f"Data size ({len(data)} bytes) exceeds block size "
                f"({self.block_size} bytes)"
            )

        self.blocks[block_num] = bytes(data)
        self.metadata["total_writes"] += 1
        self.block_access_times[block_num] = time.time()
        return True

    # --------------------------------------------------------------------- #
    #  Batch I/O
    # --------------------------------------------------------------------- #

    def read_blocks(self, block_list: List[int]) -> List[Optional[bytes]]:
        """
        Read multiple blocks at once.

        Invalid block numbers are skipped with a warning logged; their
        corresponding position in the returned list will contain None.

        Args:
            block_list (list[int]): Ordered list of block numbers to read.

        Returns:
            list[bytes | None]: Block data in the same order as the input.
                None appears for both empty blocks and skipped invalid indices.
        """
        results: List[Optional[bytes]] = []
        for block_num in block_list:
            if not (0 <= block_num < self.total_blocks):
                logger.warning(
                    "read_blocks: skipping invalid block number %d "
                    "(valid range [0, %d))", block_num, self.total_blocks
                )
                results.append(None)
                continue
            results.append(self.read_block(block_num))
        return results

    def write_blocks(self, block_data_map: Dict[int, bytes]) -> Dict[int, bool]:
        """
        Write data to multiple blocks in one call.

        Each entry is attempted independently; a failure in one block
        does not prevent the others from being written.

        Args:
            block_data_map (dict[int, bytes]): Mapping of
                {block_num: data, ...} to write.

        Returns:
            dict[int, bool]: Mapping of {block_num: success_status, ...}.
                True if the write succeeded, False otherwise.
        """
        results: Dict[int, bool] = {}
        for block_num, data in block_data_map.items():
            try:
                results[block_num] = self.write_block(block_num, data)
            except (IndexError, TypeError, ValueError) as exc:
                logger.warning(
                    "write_blocks: block %d failed — %s", block_num, exc
                )
                results[block_num] = False
        return results

    # --------------------------------------------------------------------- #
    #  Persistence
    # --------------------------------------------------------------------- #

    def save_to_file(self, filepath: str) -> bool:
        """
        Persist the entire disk state to a file using pickle.

        Saves blocks, block_access_times, metadata, and configuration
        (total_blocks, block_size). Creates parent directories if they
        do not already exist.

        Args:
            filepath (str): Destination file path (e.g. 'data/disk.img').

        Returns:
            bool: True on success, False on failure.
        """
        try:
            # Ensure the parent directory exists
            directory = os.path.dirname(filepath)
            if directory:
                os.makedirs(directory, exist_ok=True)

            state = {
                "total_blocks": self.total_blocks,
                "block_size": self.block_size,
                "blocks": self.blocks,
                "block_access_times": self.block_access_times,
                "metadata": self.metadata,
            }

            with open(filepath, "wb") as f:
                pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info("Disk state saved to %s", filepath)
            return True

        except (OSError, pickle.PicklingError) as exc:
            logger.error("Failed to save disk state to %s: %s", filepath, exc)
            return False

    @classmethod
    def load_from_file(cls, filepath: str) -> "Disk":
        """
        Load a disk from a previously saved file.

        Restores all state including blocks, metadata, access times,
        and configuration. Returns a fully re-hydrated Disk instance.

        Args:
            filepath (str): Path to the saved disk file.

        Returns:
            Disk: A new Disk instance with restored state.

        Raises:
            FileNotFoundError: If filepath does not exist.
            ValueError: If the file contains invalid or corrupt data.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Disk file not found: {filepath}")

        try:
            with open(filepath, "rb") as f:
                state = pickle.load(f)

            # Validate required keys
            required_keys = {"total_blocks", "block_size", "blocks", "metadata"}
            if not required_keys.issubset(state.keys()):
                missing = required_keys - state.keys()
                raise ValueError(f"Corrupt disk file — missing keys: {missing}")

            # Create a new instance bypassing __init__ validation overhead
            disk = cls.__new__(cls)
            disk.total_blocks = state["total_blocks"]
            disk.block_size = state["block_size"]
            disk.blocks = state["blocks"]
            disk.metadata = state["metadata"]
            disk.block_access_times = state.get("block_access_times", {})

            logger.info("Disk state loaded from %s", filepath)
            return disk

        except (pickle.UnpicklingError, KeyError) as exc:
            raise ValueError(f"Failed to load disk from {filepath}: {exc}") from exc

    # --------------------------------------------------------------------- #
    #  Block Inspection
    # --------------------------------------------------------------------- #

    def get_block_status(self, block_num: int) -> dict:
        """
        Return detailed status information for a specific block.

        Args:
            block_num (int): Zero-based index of the block to inspect.

        Returns:
            dict: A dictionary containing:
                - block_num (int):        The queried block number.
                - is_allocated (bool):    True if the block contains data.
                - size_used (int):        Bytes stored (0 if unallocated).
                - last_accessed (float | None): Timestamp of last read/write,
                      or None if the block has never been accessed.

        Raises:
            IndexError: If block_num is outside [0, total_blocks).
        """
        if not (0 <= block_num < self.total_blocks):
            raise IndexError(
                f"Block number {block_num} out of range [0, {self.total_blocks})"
            )

        data = self.blocks[block_num]
        return {
            "block_num": block_num,
            "is_allocated": data is not None,
            "size_used": len(data) if data is not None else 0,
            "last_accessed": self.block_access_times.get(block_num),
        }

    # --------------------------------------------------------------------- #
    #  Disk Information
    # --------------------------------------------------------------------- #

    def get_disk_info(self) -> dict:
        """
        Return a dictionary of disk statistics.

        Returns:
            dict: A dictionary containing:
                - total_blocks (int):    Total number of blocks.
                - block_size (int):      Size of each block in bytes.
                - total_capacity_mb (float): Total disk capacity in megabytes.
                - blocks_used (int):     Number of non-empty blocks.
                - blocks_free (int):     Number of empty blocks.
                - total_reads (int):     Cumulative read operations.
                - total_writes (int):    Cumulative write operations.
        """
        blocks_used = sum(1 for b in self.blocks if b is not None)
        total_capacity_mb = (self.total_blocks * self.block_size) / (1024 * 1024)

        return {
            "total_blocks": self.total_blocks,
            "block_size": self.block_size,
            "total_capacity_mb": total_capacity_mb,
            "blocks_used": blocks_used,
            "blocks_free": self.total_blocks - blocks_used,
            "total_reads": self.metadata["total_reads"],
            "total_writes": self.metadata["total_writes"],
        }

    # --------------------------------------------------------------------- #
    #  Disk Management
    # --------------------------------------------------------------------- #

    def format_disk(self):
        """
        Format the disk by clearing all blocks and resetting I/O counters.

        All blocks are set back to None (empty). The read and write
        counters are reset to zero, but the original creation_time
        is preserved. Block access times are also cleared.
        """
        self.blocks = [None] * self.total_blocks
        self.block_access_times.clear()
        self.metadata["total_writes"] = 0
        self.metadata["total_reads"] = 0
        logger.info("Disk formatted — all blocks cleared")

    # --------------------------------------------------------------------- #
    #  Dunder helpers
    # --------------------------------------------------------------------- #

    def __repr__(self):
        info = self.get_disk_info()
        return (
            f"Disk(total_blocks={self.total_blocks}, "
            f"block_size={self.block_size}, "
            f"used={info['blocks_used']}/{self.total_blocks})"
        )
