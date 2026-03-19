"""
inode.py - Inode (index node) metadata module.

Provides an Inode class that stores all metadata for a single file
or directory in the simulated file system, including timestamps,
permissions, size tracking, and multi-level block pointers.
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

from ..utils.constants import FileSystemConfig

logger = logging.getLogger(__name__)

# Maximum number of direct block pointers per inode
_MAX_DIRECT = FileSystemConfig.MAX_DIRECT_POINTERS


class Inode:
    """
    Represents a single inode (index node) in the file system.

    An inode stores all metadata about a file or directory —
    everything *except* the file's name (which lives in the
    parent directory entry).

    Attributes:
        inode_number (int): Unique identifier for this inode.
        file_type (str): Either ``'file'`` or ``'directory'``.
        size_bytes (int): Logical file size in bytes.
        block_count (int): Number of disk blocks occupied.
        created_time (datetime): When the inode was created.
        modified_time (datetime): Last content modification.
        accessed_time (datetime): Last access (read or write).
        permissions (str): Simple permission string (e.g. ``'rwx'``).
        owner (str): Owner name.
        direct_pointers (list[int]): Up to 12 direct block pointers.
        single_indirect (int | None): Pointer to a single-indirect block.
        double_indirect (int | None): Pointer to a double-indirect block.
        link_count (int): Number of hard links referencing this inode.
        indirect_blocks_data (dict): Simulates on-disk indirect block
            content. Structure::

                {
                    'single': [int, ...],       # pointers from single indirect block
                    'double': {                  # keyed by indirect block number
                        int: [int, ...],
                    }
                }
    """

    def __init__(self, inode_number: int, file_type: str = "file",
                 size: int = 0):
        """
        Initialize a new inode.

        Args:
            inode_number (int): Unique inode identifier.
            file_type (str): ``'file'`` or ``'directory'``.
            size (int): Initial logical size in bytes (>= 0).

        Raises:
            ValueError: If *file_type* is not ``'file'`` or
                ``'directory'``, or if *size* is negative.
        """
        if file_type not in ("file", "directory"):
            raise ValueError(
                f"file_type must be 'file' or 'directory', got '{file_type}'"
            )
        if size < 0:
            raise ValueError(f"size must be >= 0, got {size}")

        self.inode_number: int = inode_number
        self.file_type: str = file_type
        self.size_bytes: int = size
        self.block_count: int = math.ceil(
            size / FileSystemConfig.DEFAULT_BLOCK_SIZE
        ) if size > 0 else 0

        # Timestamps
        now = datetime.now()
        self.created_time: datetime = now
        self.modified_time: datetime = now
        self.accessed_time: datetime = now

        # Permissions & ownership
        self.permissions: str = "rwx"
        self.owner: str = "user"

        # Block pointers
        self.direct_pointers: List[int] = []
        self.single_indirect: Optional[int] = None
        self.double_indirect: Optional[int] = None

        # Simulated on-disk indirect block content
        self.indirect_blocks_data: Dict = {
            "single": [],
            "double": {},
        }

        # Hard-link count
        self.link_count: int = 1

    # ------------------------------------------------------------------ #
    #  Block pointer management
    # ------------------------------------------------------------------ #

    def add_block_pointer(self, block_num: int,
                          pointer_type: str = "direct") -> bool:
        """
        Add a block pointer to this inode.

        Args:
            block_num (int): The disk block number to reference.
            pointer_type (str): One of ``'direct'``,
                ``'single_indirect'``, or ``'double_indirect'``.

        Returns:
            bool: True if the pointer was added successfully.
                False if the direct-pointer list is already full
                (12 entries) or the pointer_type is unrecognised.
        """
        if pointer_type == "direct":
            if len(self.direct_pointers) >= _MAX_DIRECT:
                logger.warning(
                    "Inode %d: direct pointers full (%d/%d)",
                    self.inode_number, len(self.direct_pointers), _MAX_DIRECT,
                )
                return False
            self.direct_pointers.append(block_num)
            self.update_modified_time()
            return True

        elif pointer_type == "single_indirect":
            self.single_indirect = block_num
            self.update_modified_time()
            return True

        elif pointer_type == "double_indirect":
            self.double_indirect = block_num
            self.update_modified_time()
            return True

        else:
            logger.warning(
                "Inode %d: unknown pointer_type '%s'",
                self.inode_number, pointer_type,
            )
            return False

    def get_all_block_pointers(self) -> List[int]:
        """
        Return a flat, sorted list of **all data-block** pointers.

        This includes:
          1. Direct pointers.
          2. Pointers stored inside the single-indirect block.
          3. Pointers stored inside every double-indirect block.

        Note: the indirect/double-indirect *index* blocks themselves
        are **not** included — only the data-block pointers they hold.

        Returns:
            list[int]: Sorted list of unique data-block numbers.
        """
        pointers: List[int] = list(self.direct_pointers)

        # Single-indirect data pointers
        pointers.extend(self.indirect_blocks_data.get("single", []))

        # Double-indirect data pointers
        for blk_list in self.indirect_blocks_data.get("double", {}).values():
            pointers.extend(blk_list)

        return sorted(set(pointers))

    def set_single_indirect_block(self, block_num: int,
                                   pointers: List[int]) -> bool:
        """
        Set the single-indirect block and its contained pointers.

        In a real file system the *pointers* list would be written to
        the disk block identified by *block_num*. Here we store them
        in ``indirect_blocks_data['single']`` for simulation.

        Args:
            block_num (int): The disk block used as the indirect block.
            pointers (list[int]): Data-block pointers stored in that block.

        Returns:
            bool: True on success.
        """
        ppb = self._get_pointers_per_block()
        if len(pointers) > ppb:
            logger.warning(
                "Inode %d: single-indirect pointers (%d) exceed "
                "max per block (%d)",
                self.inode_number, len(pointers), ppb,
            )
            return False

        self.single_indirect = block_num
        self.indirect_blocks_data["single"] = list(pointers)
        self.update_modified_time()
        logger.debug(
            "Inode %d: single-indirect block set to %d (%d pointers)",
            self.inode_number, block_num, len(pointers),
        )
        return True

    def set_double_indirect_block(
        self, block_num: int,
        indirect_blocks: Dict[int, List[int]],
    ) -> bool:
        """
        Set the double-indirect block and its mapping of indirect blocks.

        Args:
            block_num (int): The disk block used as the double-indirect
                index block.
            indirect_blocks (dict[int, list[int]]): Mapping of
                ``{indirect_block_num: [data_block_ptr, ...], ...}``.

        Returns:
            bool: True on success.
        """
        ppb = self._get_pointers_per_block()
        if len(indirect_blocks) > ppb:
            logger.warning(
                "Inode %d: double-indirect entries (%d) exceed "
                "max per block (%d)",
                self.inode_number, len(indirect_blocks), ppb,
            )
            return False

        self.double_indirect = block_num
        self.indirect_blocks_data["double"] = {
            k: list(v) for k, v in indirect_blocks.items()
        }
        self.update_modified_time()
        logger.debug(
            "Inode %d: double-indirect block set to %d (%d indirect blocks)",
            self.inode_number, block_num, len(indirect_blocks),
        )
        return True

    # ------------------------------------------------------------------ #
    #  Block index helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_pointers_per_block(
        block_size: int = FileSystemConfig.DEFAULT_BLOCK_SIZE,
    ) -> int:
        """
        Calculate how many 4-byte block pointers fit in one block.

        Args:
            block_size (int): Block size in bytes.

        Returns:
            int: Number of pointers per block (``block_size // 4``).
        """
        return block_size // 4

    @staticmethod
    def calculate_max_file_size(
        block_size: int = FileSystemConfig.DEFAULT_BLOCK_SIZE,
    ) -> int:
        """
        Calculate the maximum file size supported by the inode structure.

        Layout::

            Direct:          12 blocks
            Single indirect: 1 block holding (block_size / 4) pointers
            Double indirect:  1 block → (block_size / 4) indirect blocks
                              each holding (block_size / 4) pointers

        Args:
            block_size (int): Block size in bytes.

        Returns:
            int: Maximum file size in bytes.
        """
        ppb = block_size // 4  # pointers per block

        direct_blocks = _MAX_DIRECT
        single_blocks = ppb
        double_blocks = ppb * ppb

        total_blocks = direct_blocks + single_blocks + double_blocks
        return total_blocks * block_size

    def get_pointer_type_for_block(self, block_index: int) -> str:
        """
        Determine the pointer level needed for a given logical block index.

        Args:
            block_index (int): Zero-based logical block index within the file.

        Returns:
            str: ``'direct'``, ``'single_indirect'``, or
                ``'double_indirect'``.

        Raises:
            IndexError: If *block_index* exceeds the inode's addressable
                range.
        """
        ppb = self._get_pointers_per_block()

        if block_index < _MAX_DIRECT:
            return "direct"
        elif block_index < _MAX_DIRECT + ppb:
            return "single_indirect"
        elif block_index < _MAX_DIRECT + ppb + ppb * ppb:
            return "double_indirect"
        else:
            raise IndexError(
                f"Block index {block_index} exceeds maximum addressable "
                f"range for this inode structure"
            )

    def get_block_at_index(self, block_index: int) -> Optional[int]:
        """
        Return the physical block number for a logical block index.

        Handles direct, single-indirect, and double-indirect lookups
        using the data stored in ``indirect_blocks_data``.

        Args:
            block_index (int): Zero-based logical block index.

        Returns:
            int | None: Physical block number, or None if the block
                is not allocated at that index.
        """
        ppb = self._get_pointers_per_block()

        # Direct region: indices 0 .. 11
        if block_index < _MAX_DIRECT:
            if block_index < len(self.direct_pointers):
                return self.direct_pointers[block_index]
            return None

        # Single-indirect region: indices 12 .. 12 + ppb - 1
        si_index = block_index - _MAX_DIRECT
        if si_index < ppb:
            single_ptrs = self.indirect_blocks_data.get("single", [])
            if si_index < len(single_ptrs):
                return single_ptrs[si_index]
            return None

        # Double-indirect region
        di_offset = block_index - _MAX_DIRECT - ppb
        if di_offset < ppb * ppb:
            # Which indirect block within the double-indirect table?
            indirect_idx = di_offset // ppb
            ptr_idx = di_offset % ppb

            double_data = self.indirect_blocks_data.get("double", {})
            # Indirect blocks are keyed by their block number; we iterate
            # in sorted order to provide deterministic indexing.
            sorted_keys = sorted(double_data.keys())
            if indirect_idx < len(sorted_keys):
                key = sorted_keys[indirect_idx]
                ptrs = double_data[key]
                if ptr_idx < len(ptrs):
                    return ptrs[ptr_idx]
            return None

        return None

    # ------------------------------------------------------------------ #
    #  Timestamp management
    # ------------------------------------------------------------------ #

    def update_access_time(self) -> None:
        """Set ``accessed_time`` to the current datetime."""
        self.accessed_time = datetime.now()

    def update_modified_time(self) -> None:
        """
        Set ``modified_time`` to the current datetime.

        Also updates ``accessed_time``, since a modification implies
        an access.
        """
        now = datetime.now()
        self.modified_time = now
        self.accessed_time = now

    # ------------------------------------------------------------------ #
    #  Size management
    # ------------------------------------------------------------------ #

    def update_size(self, new_size: int) -> None:
        """
        Update the logical file size and recalculate block count.

        Args:
            new_size (int): New size in bytes (must be >= 0).

        Raises:
            ValueError: If *new_size* is negative.
        """
        if new_size < 0:
            raise ValueError(f"new_size must be >= 0, got {new_size}")

        self.size_bytes = new_size
        self.block_count = math.ceil(
            new_size / FileSystemConfig.DEFAULT_BLOCK_SIZE
        ) if new_size > 0 else 0
        self.update_modified_time()

    # ------------------------------------------------------------------ #
    #  Serialization / deserialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict:
        """
        Serialize the inode to a plain dictionary.

        Datetime values are converted to ISO-8601 strings for
        JSON-safe storage.

        Returns:
            dict: All inode attributes in serializable form.
        """
        # Serialise double-indirect keys as strings for JSON compat
        double_data = {
            str(k): list(v)
            for k, v in self.indirect_blocks_data.get("double", {}).items()
        }
        return {
            "inode_number": self.inode_number,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "block_count": self.block_count,
            "created_time": self.created_time.isoformat(),
            "modified_time": self.modified_time.isoformat(),
            "accessed_time": self.accessed_time.isoformat(),
            "permissions": self.permissions,
            "owner": self.owner,
            "direct_pointers": list(self.direct_pointers),
            "single_indirect": self.single_indirect,
            "double_indirect": self.double_indirect,
            "link_count": self.link_count,
            "indirect_blocks_data": {
                "single": list(self.indirect_blocks_data.get("single", [])),
                "double": double_data,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Inode":
        """
        Deserialize an inode from a dictionary.

        Args:
            data (dict): Dictionary produced by ``to_dict()``.

        Returns:
            Inode: A fully restored Inode instance.
        """
        inode = cls.__new__(cls)
        inode.inode_number = data["inode_number"]
        inode.file_type = data["file_type"]
        inode.size_bytes = data["size_bytes"]
        inode.block_count = data["block_count"]
        inode.created_time = datetime.fromisoformat(data["created_time"])
        inode.modified_time = datetime.fromisoformat(data["modified_time"])
        inode.accessed_time = datetime.fromisoformat(data["accessed_time"])
        inode.permissions = data.get("permissions", "rwx")
        inode.owner = data.get("owner", "user")
        inode.direct_pointers = list(data.get("direct_pointers", []))
        inode.single_indirect = data.get("single_indirect")
        inode.double_indirect = data.get("double_indirect")
        inode.link_count = data.get("link_count", 1)

        # Restore indirect_blocks_data (convert string keys back to int)
        raw = data.get("indirect_blocks_data", {"single": [], "double": {}})
        inode.indirect_blocks_data = {
            "single": list(raw.get("single", [])),
            "double": {
                int(k): list(v)
                for k, v in raw.get("double", {}).items()
            },
        }
        return inode

    # ------------------------------------------------------------------ #
    #  Dunder helpers
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"Inode(num={self.inode_number}, type={self.file_type}, "
            f"size={self.size_bytes}, blocks={self.block_count})"
        )
