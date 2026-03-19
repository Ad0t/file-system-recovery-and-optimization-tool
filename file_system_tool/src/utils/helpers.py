"""
helpers.py - Utility helper functions for the file system simulator.

Provides conversion, validation, and path manipulation utilities
used across multiple modules.
"""

import math
from .constants import DEFAULT_BLOCK_SIZE, MAX_FILE_NAME_LENGTH


# =============================================================================
# Block / Byte Conversion Helpers
# =============================================================================

def bytes_to_blocks(size_bytes, block_size=DEFAULT_BLOCK_SIZE):
    """
    Calculate the number of blocks needed to store a given number of bytes.

    Uses ceiling division so that any partial block still counts as one full
    block (a file of 4097 bytes on a 4096-byte block disk needs 2 blocks).

    Args:
        size_bytes (int): Size in bytes (must be >= 0).
        block_size (int): Size of each block in bytes (must be > 0).

    Returns:
        int: Number of blocks required (minimum 0).

    Raises:
        ValueError: If size_bytes is negative or block_size is not positive.

    Examples:
        >>> bytes_to_blocks(4096)
        1
        >>> bytes_to_blocks(4097)
        2
        >>> bytes_to_blocks(0)
        0
    """
    if size_bytes < 0:
        raise ValueError(f"size_bytes must be >= 0, got {size_bytes}")
    if block_size <= 0:
        raise ValueError(f"block_size must be > 0, got {block_size}")
    return math.ceil(size_bytes / block_size)


def blocks_to_bytes(num_blocks, block_size=DEFAULT_BLOCK_SIZE):
    """
    Convert a number of blocks to the total byte capacity.

    This gives the *maximum* number of bytes that can be stored in
    the given number of blocks (i.e. num_blocks * block_size).

    Args:
        num_blocks (int): Number of blocks (must be >= 0).
        block_size (int): Size of each block in bytes (must be > 0).

    Returns:
        int: Total bytes.

    Raises:
        ValueError: If num_blocks is negative or block_size is not positive.

    Examples:
        >>> blocks_to_bytes(1)
        4096
        >>> blocks_to_bytes(2, block_size=512)
        1024
        >>> blocks_to_bytes(0)
        0
    """
    if num_blocks < 0:
        raise ValueError(f"num_blocks must be >= 0, got {num_blocks}")
    if block_size <= 0:
        raise ValueError(f"block_size must be > 0, got {block_size}")
    return num_blocks * block_size


# =============================================================================
# Formatting Helpers
# =============================================================================

def format_size(size_bytes):
    """
    Format a byte count into a human-readable string.

    Args:
        size_bytes (int): Size in bytes.

    Returns:
        str: Human-readable size string (e.g., '4.0 KB').
    """
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    i = min(i, len(units) - 1)
    size = size_bytes / (1024 ** i)
    return f"{size:.1f} {units[i]}"


# =============================================================================
# Validation Helpers
# =============================================================================

def validate_filename(name):
    """
    Validate a file or directory name.

    Args:
        name (str): The name to validate.

    Returns:
        bool: True if the name is valid.

    Raises:
        ValueError: If the name is invalid (with reason).
    """
    if not name:
        raise ValueError("File name cannot be empty")
    if len(name) > MAX_FILE_NAME_LENGTH:
        raise ValueError(f"File name exceeds maximum length of {MAX_FILE_NAME_LENGTH}")
    invalid_chars = ['/', '\\', '\0', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in name:
            raise ValueError(f"File name contains invalid character: '{char}'")
    if name in ('.', '..'):
        raise ValueError(f"'{name}' is a reserved name")
    return True


# =============================================================================
# Path Helpers
# =============================================================================

def split_path(path):
    """
    Split a file path into its components.

    Args:
        path (str): The path to split (e.g., '/home/user/file.txt').

    Returns:
        list[str]: List of path components.
    """
    parts = path.strip("/").split("/")
    return [p for p in parts if p]


def join_path(*parts):
    """
    Join path components into a single path.

    Args:
        *parts: Path components.

    Returns:
        str: Joined path string.
    """
    return "/" + "/".join(p.strip("/") for p in parts if p)
