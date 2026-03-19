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
        Return a flat list of all block pointers held by this inode.

        Currently returns direct pointers only. Indirect-block
        traversal will be added in a future step.

        Returns:
            list[int]: Ordered list of block numbers.
        """
        pointers = list(self.direct_pointers)

        if self.single_indirect is not None:
            pointers.append(self.single_indirect)

        if self.double_indirect is not None:
            pointers.append(self.double_indirect)

        return pointers

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
        return inode

    # ------------------------------------------------------------------ #
    #  Dunder helpers
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"Inode(num={self.inode_number}, type={self.file_type}, "
            f"size={self.size_bytes}, blocks={self.block_count})"
        )
