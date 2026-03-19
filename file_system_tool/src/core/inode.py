"""
inode.py - Inode management module.

Provides Inode and InodeTable classes for managing file metadata
in the simulated file system.
"""

import time
from ..utils.constants import INODE_TYPE_FILE, INODE_TYPE_DIRECTORY, MAX_DIRECT_BLOCKS


class Inode:
    """Represents a single inode (index node) storing file/directory metadata."""

    _next_id = 0

    def __init__(self, inode_type=INODE_TYPE_FILE, permissions=0o644):
        """
        Initialize an inode.

        Args:
            inode_type (int): Type of inode (file or directory).
            permissions (int): Unix-style permission bits.
        """
        self.inode_id = Inode._next_id
        Inode._next_id += 1

        self.inode_type = inode_type
        self.permissions = permissions
        self.size = 0
        self.direct_blocks = []  # List of block numbers
        self.indirect_block = None  # Block number for indirect pointer block
        self.link_count = 1
        self.created_at = time.time()
        self.modified_at = self.created_at
        self.accessed_at = self.created_at

    def add_block(self, block_num):
        """
        Add a block number to this inode's allocation list.

        Args:
            block_num (int): The block number to add.

        Returns:
            bool: True if block was added successfully.
        """
        if len(self.direct_blocks) < MAX_DIRECT_BLOCKS:
            self.direct_blocks.append(block_num)
            self.modified_at = time.time()
            return True
        return False

    def remove_block(self, block_num):
        """
        Remove a block number from this inode's allocation list.

        Args:
            block_num (int): The block number to remove.
        """
        if block_num in self.direct_blocks:
            self.direct_blocks.remove(block_num)
            self.modified_at = time.time()

    def update_access_time(self):
        """Update the last accessed timestamp."""
        self.accessed_at = time.time()

    def update_modification_time(self):
        """Update the last modified timestamp."""
        self.modified_at = time.time()

    @property
    def is_file(self):
        return self.inode_type == INODE_TYPE_FILE

    @property
    def is_directory(self):
        return self.inode_type == INODE_TYPE_DIRECTORY

    def __repr__(self):
        type_str = "FILE" if self.is_file else "DIR"
        return f"Inode(id={self.inode_id}, type={type_str}, size={self.size}, blocks={len(self.direct_blocks)})"


class InodeTable:
    """Manages a collection of inodes."""

    def __init__(self, max_inodes=256):
        """
        Initialize the inode table.

        Args:
            max_inodes (int): Maximum number of inodes.
        """
        self.max_inodes = max_inodes
        self.inodes = {}  # inode_id -> Inode

    def allocate_inode(self, inode_type=INODE_TYPE_FILE, permissions=0o644):
        """
        Allocate a new inode.

        Args:
            inode_type (int): Type of inode.
            permissions (int): Permission bits.

        Returns:
            Inode | None: The allocated inode, or None if table is full.
        """
        if len(self.inodes) >= self.max_inodes:
            return None
        inode = Inode(inode_type, permissions)
        self.inodes[inode.inode_id] = inode
        return inode

    def free_inode(self, inode_id):
        """
        Free an inode by its ID.

        Args:
            inode_id (int): The inode ID to free.

        Returns:
            bool: True if the inode was freed.
        """
        if inode_id in self.inodes:
            del self.inodes[inode_id]
            return True
        return False

    def get_inode(self, inode_id):
        """
        Retrieve an inode by its ID.

        Args:
            inode_id (int): The inode ID.

        Returns:
            Inode | None: The inode, or None if not found.
        """
        return self.inodes.get(inode_id)

    def __len__(self):
        return len(self.inodes)

    def __repr__(self):
        return f"InodeTable(used={len(self.inodes)}, max={self.max_inodes})"
