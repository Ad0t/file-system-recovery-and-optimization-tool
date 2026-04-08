"""
constants.py - System-wide constants and configuration for the file system simulator.

This module defines all configuration values, enumerations, and limits
used throughout the simulated file system. Constants are organized into
a central FileSystemConfig class and supporting enums.
"""

from enum import Enum, auto


# =============================================================================
# Enumerations
# =============================================================================

class AllocationMethod(Enum):
    """
    File allocation strategies supported by the simulator.

    - CONTIGUOUS: All blocks for a file are stored sequentially on disk.
                  Fast reads, but suffers from external fragmentation.
    - LINKED:     Each block contains a pointer to the next block in the chain.
                  No external fragmentation, but slow random access.
    - INDEXED:    An index block holds pointers to all data blocks.
                  Supports direct access without fragmentation overhead.
    """
    CONTIGUOUS = auto()
    LINKED = auto()
    INDEXED = auto()


class OperationType(Enum):
    """
    Types of file system operations that can be performed.

    Used by the journal and logging subsystem to track
    what kind of operation was requested.
    """
    CREATE = auto()   # Create a new file
    DELETE = auto()   # Delete an existing file
    WRITE = auto()    # Write data to a file
    READ = auto()     # Read data from a file
    MKDIR = auto()    # Create a new directory
    RMDIR = auto()    # Remove an existing directory


# =============================================================================
# Configuration Class
# =============================================================================

class FileSystemConfig:
    """
    Central configuration class holding all file system simulator constants.

    All values are class-level attributes, so they can be accessed without
    instantiation:  FileSystemConfig.DEFAULT_BLOCK_SIZE
    """

    # ---- Block Configuration ------------------------------------------------
    # The fundamental unit of storage. All reads/writes operate on whole blocks.
    DEFAULT_BLOCK_SIZE = 4096          # 4 KB per block

    # ---- Disk Size Presets --------------------------------------------------
    # Pre-defined disk sizes expressed as a number of blocks.
    # Total bytes = num_blocks * DEFAULT_BLOCK_SIZE
    SMALL_DISK = 1024                  # 1,024 blocks  →   4 MB
    MEDIUM_DISK = 262144               # 262,144 blocks → 1 GB
    LARGE_DISK = 1048576               # 1,048,576 blocks → 4 GB

    # ---- Inode Pointer Limits -----------------------------------------------
    # Controls how many data blocks a single inode can reference at each level.
    #   Direct pointers   → stored in the inode itself (fastest access)
    #   Single indirect   → one intermediate index block
    #   Double indirect   → two levels of index blocks
    MAX_DIRECT_POINTERS = 12           # 12 direct block pointers per inode
    MAX_SINGLE_INDIRECT = 256          # Pointers in a single-indirect block
    MAX_DOUBLE_INDIRECT = 65536        # Pointers reachable via double-indirect

    # ---- Inode Table Limits -------------------------------------------------
    MAX_INODES = 256                   # Maximum number of inodes in the table

    # ---- File Name Limits ---------------------------------------------------
    MAX_FILE_NAME_LENGTH = 255         # Maximum characters in a file/dir name

    # ---- Journal Configuration ----------------------------------------------
    # The journal records pending operations for crash recovery.
    JOURNAL_MAX_ENTRIES = 1000         # Max entries before oldest are trimmed

    # ---- FAT Special Sentinel Values ----------------------------------------
    # Used in the File Allocation Table to mark block status.
    FAT_FREE = -1                      # Block is unallocated / available
    FAT_EOF = -2                       # Marks the last block of a file chain
    FAT_BAD = -3                       # Block is damaged and unusable

    # ---- Inode Type Identifiers ---------------------------------------------
    INODE_TYPE_FILE = 0                # Inode represents a regular file
    INODE_TYPE_DIRECTORY = 1           # Inode represents a directory


# =============================================================================
# Backward-compatible module-level aliases
# =============================================================================
# These allow existing code to keep using:
#   from utils.constants import DEFAULT_BLOCK_SIZE
# without any import changes.

DEFAULT_BLOCK_SIZE = FileSystemConfig.DEFAULT_BLOCK_SIZE
DEFAULT_NUM_BLOCKS = FileSystemConfig.SMALL_DISK  # Default disk = SMALL preset

MAX_FILE_NAME_LENGTH = FileSystemConfig.MAX_FILE_NAME_LENGTH

INODE_TYPE_FILE = FileSystemConfig.INODE_TYPE_FILE
INODE_TYPE_DIRECTORY = FileSystemConfig.INODE_TYPE_DIRECTORY
MAX_DIRECT_BLOCKS = FileSystemConfig.MAX_DIRECT_POINTERS
MAX_INODES = FileSystemConfig.MAX_INODES

FAT_FREE = FileSystemConfig.FAT_FREE
FAT_EOF = FileSystemConfig.FAT_EOF
FAT_BAD = FileSystemConfig.FAT_BAD

MAX_JOURNAL_ENTRIES = FileSystemConfig.JOURNAL_MAX_ENTRIES
