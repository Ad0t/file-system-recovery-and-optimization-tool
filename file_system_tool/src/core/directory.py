"""
directory.py - Directory management module.

Provides DirectoryEntry and Directory classes for managing
the hierarchical directory structure of the file system.
"""

from ..utils.constants import INODE_TYPE_DIRECTORY, INODE_TYPE_FILE


class DirectoryEntry:
    """Represents a single entry in a directory (file or subdirectory)."""

    def __init__(self, name, inode_id, entry_type=INODE_TYPE_FILE):
        """
        Initialize a directory entry.

        Args:
            name (str): Name of the file or directory.
            inode_id (int): Associated inode ID.
            entry_type (int): Type of entry (file or directory).
        """
        self.name = name
        self.inode_id = inode_id
        self.entry_type = entry_type

    @property
    def is_file(self):
        return self.entry_type == INODE_TYPE_FILE

    @property
    def is_directory(self):
        return self.entry_type == INODE_TYPE_DIRECTORY

    def __repr__(self):
        type_str = "FILE" if self.is_file else "DIR"
        return f"DirectoryEntry(name='{self.name}', inode={self.inode_id}, type={type_str})"


class Directory:
    """Represents a directory containing entries (files and subdirectories)."""

    def __init__(self, name, inode_id, parent=None):
        """
        Initialize a directory.

        Args:
            name (str): Name of the directory.
            inode_id (int): Inode ID of this directory.
            parent (Directory | None): Parent directory (None for root).
        """
        self.name = name
        self.inode_id = inode_id
        self.parent = parent
        self.entries = {}  # name -> DirectoryEntry

    def add_entry(self, name, inode_id, entry_type=INODE_TYPE_FILE):
        """
        Add an entry to this directory.

        Args:
            name (str): Name of the entry.
            inode_id (int): Inode ID of the entry.
            entry_type (int): Type of the entry.

        Returns:
            DirectoryEntry | None: The created entry, or None if name exists.
        """
        if name in self.entries:
            return None
        entry = DirectoryEntry(name, inode_id, entry_type)
        self.entries[name] = entry
        return entry

    def remove_entry(self, name):
        """
        Remove an entry from this directory.

        Args:
            name (str): Name of the entry to remove.

        Returns:
            DirectoryEntry | None: The removed entry, or None if not found.
        """
        return self.entries.pop(name, None)

    def get_entry(self, name):
        """
        Look up an entry by name.

        Args:
            name (str): Name of the entry.

        Returns:
            DirectoryEntry | None: The entry, or None if not found.
        """
        return self.entries.get(name)

    def list_entries(self):
        """
        List all entries in this directory.

        Returns:
            list[DirectoryEntry]: List of directory entries.
        """
        return list(self.entries.values())

    def get_path(self):
        """
        Get the full path of this directory.

        Returns:
            str: Full path from root.
        """
        if self.parent is None:
            return "/"
        parts = []
        current = self
        while current is not None and current.parent is not None:
            parts.append(current.name)
            current = current.parent
        return "/" + "/".join(reversed(parts))

    def __len__(self):
        return len(self.entries)

    def __repr__(self):
        return f"Directory(name='{self.name}', entries={len(self.entries)})"
