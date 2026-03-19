"""
journal.py - Journaling module for crash recovery.

Provides a Journal class that logs file system operations
to enable recovery after unexpected failures.
"""

import time
from enum import Enum


class JournalEntryType(Enum):
    """Types of journal entries."""
    CREATE = "CREATE"
    DELETE = "DELETE"
    WRITE = "WRITE"
    RENAME = "RENAME"
    MKDIR = "MKDIR"
    RMDIR = "RMDIR"
    ALLOCATE = "ALLOCATE"
    FREE = "FREE"


class JournalEntryStatus(Enum):
    """Status of a journal entry."""
    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class JournalEntry:
    """Represents a single journal entry."""

    _next_id = 0

    def __init__(self, entry_type, description, metadata=None):
        """
        Initialize a journal entry.

        Args:
            entry_type (JournalEntryType): Type of operation.
            description (str): Human-readable description.
            metadata (dict | None): Additional operation-specific data.
        """
        self.entry_id = JournalEntry._next_id
        JournalEntry._next_id += 1

        self.entry_type = entry_type
        self.description = description
        self.metadata = metadata or {}
        self.status = JournalEntryStatus.PENDING
        self.timestamp = time.time()

    def commit(self):
        """Mark this entry as committed."""
        self.status = JournalEntryStatus.COMMITTED

    def rollback(self):
        """Mark this entry as rolled back."""
        self.status = JournalEntryStatus.ROLLED_BACK

    def __repr__(self):
        return (f"JournalEntry(id={self.entry_id}, type={self.entry_type.value}, "
                f"status={self.status.value})")


class Journal:
    """File system journal for tracking operations and enabling recovery."""

    def __init__(self, max_entries=1024):
        """
        Initialize the journal.

        Args:
            max_entries (int): Maximum number of entries to retain.
        """
        self.max_entries = max_entries
        self.entries = []
        self.checkpoint_id = 0

    def log(self, entry_type, description, metadata=None):
        """
        Log a new operation to the journal.

        Args:
            entry_type (JournalEntryType): Type of operation.
            description (str): Description of the operation.
            metadata (dict | None): Additional data.

        Returns:
            JournalEntry: The created journal entry.
        """
        entry = JournalEntry(entry_type, description, metadata)
        self.entries.append(entry)
        # Trim old entries if over the limit
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        return entry

    def commit(self, entry_id):
        """
        Commit a specific journal entry.

        Args:
            entry_id (int): The entry ID to commit.

        Returns:
            bool: True if the entry was found and committed.
        """
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.commit()
                return True
        return False

    def rollback(self, entry_id):
        """
        Roll back a specific journal entry.

        Args:
            entry_id (int): The entry ID to roll back.

        Returns:
            bool: True if the entry was found and rolled back.
        """
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.rollback()
                return True
        return False

    def get_pending_entries(self):
        """
        Get all pending (uncommitted) journal entries.

        Returns:
            list[JournalEntry]: List of pending entries.
        """
        return [e for e in self.entries if e.status == JournalEntryStatus.PENDING]

    def create_checkpoint(self):
        """
        Create a checkpoint, committing all pending entries.

        Returns:
            int: The checkpoint ID.
        """
        for entry in self.get_pending_entries():
            entry.commit()
        self.checkpoint_id += 1
        return self.checkpoint_id

    def get_entries_since_checkpoint(self):
        """
        Get entries that were logged after the last checkpoint.

        Returns:
            list[JournalEntry]: List of entries since last checkpoint.
        """
        return [e for e in self.entries if e.status == JournalEntryStatus.PENDING]

    def clear(self):
        """Clear all journal entries."""
        self.entries.clear()

    def __len__(self):
        return len(self.entries)

    def __repr__(self):
        return f"Journal(entries={len(self.entries)}, checkpoint={self.checkpoint_id})"
