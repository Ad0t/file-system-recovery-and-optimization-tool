"""
journal.py - Transaction journal module.

Provides JournalEntry and Journal classes for write-ahead logging
in the simulated file system. Supports transaction begin / commit /
abort, redo / undo data, persistence to disk, checkpointing, and
crash-recovery queries.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from utils.constants import FileSystemConfig

logger = logging.getLogger(__name__)


# ===================================================================== #
#  JournalEntry
# ===================================================================== #

class JournalEntry:
    """
    A single transaction record in the journal.

    Attributes:
        transaction_id (str): Unique UUID string for this transaction.
        timestamp (datetime): When the transaction was created.
        commit_timestamp (datetime | None): When the transaction was
            committed (None while still pending).
        operation (str): Operation type, e.g. ``'CREATE'``, ``'DELETE'``,
            ``'WRITE'``, ``'READ'``, ``'MKDIR'``, ``'RMDIR'``.
        status (str): ``'PENDING'``, ``'COMMITTED'``, or ``'ABORTED'``.
        metadata (dict): Operation-specific data (paths, inode numbers,
            block lists, sizes, etc.).
        redo_data (dict): Data needed to **replay** the operation.
        undo_data (dict): Data needed to **rollback** the operation.
    """

    def __init__(self, operation: str, metadata: dict):
        """
        Create a new journal entry.

        Args:
            operation (str): Operation type string.
            metadata (dict): Arbitrary operation-specific information.
        """
        self.transaction_id: str = str(uuid.uuid4())
        self.timestamp: datetime = datetime.now()
        self.commit_timestamp: Optional[datetime] = None
        self.operation: str = operation
        self.status: str = "PENDING"
        self.metadata: dict = dict(metadata)
        self.redo_data: dict = {}
        self.undo_data: dict = {}

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def commit(self) -> None:
        """Mark this transaction as COMMITTED and record the commit time."""
        self.status = "COMMITTED"
        self.commit_timestamp = datetime.now()

    def abort(self) -> None:
        """Mark this transaction as ABORTED."""
        self.status = "ABORTED"

    # ------------------------------------------------------------------ #
    #  Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        """
        Serialize the entry to a plain dictionary.

        Returns:
            dict: JSON-safe representation.
        """
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "commit_timestamp": (
                self.commit_timestamp.isoformat()
                if self.commit_timestamp else None
            ),
            "operation": self.operation,
            "status": self.status,
            "metadata": self.metadata,
            "redo_data": self.redo_data,
            "undo_data": self.undo_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        """
        Deserialize a JournalEntry from a dictionary.

        Args:
            data (dict): Dictionary produced by ``to_dict()``.

        Returns:
            JournalEntry: Restored entry.
        """
        entry = cls.__new__(cls)
        entry.transaction_id = data["transaction_id"]
        entry.timestamp = datetime.fromisoformat(data["timestamp"])
        entry.commit_timestamp = (
            datetime.fromisoformat(data["commit_timestamp"])
            if data.get("commit_timestamp") else None
        )
        entry.operation = data["operation"]
        entry.status = data["status"]
        entry.metadata = data.get("metadata", {})
        entry.redo_data = data.get("redo_data", {})
        entry.undo_data = data.get("undo_data", {})
        return entry

    # ------------------------------------------------------------------ #
    #  Dunder
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"JournalEntry(id={self.transaction_id[:8]}…, "
            f"op={self.operation}, status={self.status})"
        )


# ===================================================================== #
#  Journal
# ===================================================================== #

class Journal:
    """
    Write-ahead transaction journal for crash recovery.

    The journal stores a chronological list of JournalEntry objects
    and can persist them to a JSON file on disk. During recovery,
    uncommitted (PENDING) transactions can be inspected and replayed
    or rolled back.

    Attributes:
        entries (list[JournalEntry]): All journal entries.
        max_entries (int): Maximum entries to retain.
        journal_file (str): Path to the on-disk journal file.
        auto_checkpoint (bool): If True, checkpoint after every commit.
    """

    def __init__(self, journal_file: str = "data/journal.log",
                 max_entries: int = FileSystemConfig.JOURNAL_MAX_ENTRIES,
                 auto_checkpoint: bool = False):
        """
        Initialize the journal.

        If *journal_file* already exists on disk the journal is loaded
        automatically.

        Args:
            journal_file (str): Path for persistence.
            max_entries (int): Maximum entries before old committed
                entries are pruned.
            auto_checkpoint (bool): Automatically checkpoint on commit.
        """
        self.entries: List[JournalEntry] = []
        self.max_entries: int = max_entries
        self.journal_file: str = journal_file
        self.auto_checkpoint: bool = auto_checkpoint

        # Attempt to load existing journal
        if os.path.exists(journal_file):
            self.load_journal()

        logger.info(
            "Journal initialized (file=%s, max=%d, auto_cp=%s)",
            journal_file, max_entries, auto_checkpoint,
        )

    # ------------------------------------------------------------------ #
    #  Internal lookup
    # ------------------------------------------------------------------ #

    def _find_entry(self, transaction_id: str) -> Optional[JournalEntry]:
        """Return the entry with the given ID, or None."""
        for entry in self.entries:
            if entry.transaction_id == transaction_id:
                return entry
        return None

    # ------------------------------------------------------------------ #
    #  Transaction lifecycle
    # ------------------------------------------------------------------ #

    def begin_transaction(self, operation: str, metadata: dict) -> str:
        """
        Start a new transaction.

        Args:
            operation (str): Operation type (e.g. ``'CREATE'``).
            metadata (dict): Operation-specific data.

        Returns:
            str: The ``transaction_id`` of the new entry.
        """
        entry = JournalEntry(operation, metadata)
        self.entries.append(entry)

        logger.debug(
            "Transaction started: %s [%s]",
            entry.transaction_id[:8], operation,
        )
        return entry.transaction_id

    def add_redo_data(self, transaction_id: str,
                      redo_data: dict) -> bool:
        """
        Attach redo information to a transaction.

        Args:
            transaction_id (str): Target transaction.
            redo_data (dict): Data needed to replay the operation.

        Returns:
            bool: True on success, False if transaction not found.
        """
        entry = self._find_entry(transaction_id)
        if entry is None:
            logger.warning(
                "add_redo_data: transaction %s not found", transaction_id[:8]
            )
            return False
        entry.redo_data.update(redo_data)
        return True

    def add_undo_data(self, transaction_id: str,
                      undo_data: dict) -> bool:
        """
        Attach undo information to a transaction.

        Args:
            transaction_id (str): Target transaction.
            undo_data (dict): Data needed to rollback the operation.

        Returns:
            bool: True on success, False if transaction not found.
        """
        entry = self._find_entry(transaction_id)
        if entry is None:
            logger.warning(
                "add_undo_data: transaction %s not found", transaction_id[:8]
            )
            return False
        entry.undo_data.update(undo_data)
        return True

    def commit_transaction(self, transaction_id: str) -> bool:
        """
        Mark a transaction as COMMITTED and persist the journal.

        Args:
            transaction_id (str): Transaction to commit.

        Returns:
            bool: True on success, False if not found.
        """
        entry = self._find_entry(transaction_id)
        if entry is None:
            logger.warning(
                "commit_transaction: %s not found", transaction_id[:8]
            )
            return False

        entry.commit()
        self.save_journal()

        if self.auto_checkpoint:
            self.checkpoint()

        logger.debug("Transaction committed: %s", transaction_id[:8])
        return True

    def abort_transaction(self, transaction_id: str) -> bool:
        """
        Mark a transaction as ABORTED.

        Args:
            transaction_id (str): Transaction to abort.

        Returns:
            bool: True on success, False if not found.
        """
        entry = self._find_entry(transaction_id)
        if entry is None:
            logger.warning(
                "abort_transaction: %s not found", transaction_id[:8]
            )
            return False

        entry.abort()
        logger.debug("Transaction aborted: %s", transaction_id[:8])
        return True

    # ------------------------------------------------------------------ #
    #  Queries
    # ------------------------------------------------------------------ #

    def get_uncommitted_transactions(self) -> List[JournalEntry]:
        """
        Return all PENDING transactions (for crash recovery).

        Returns:
            list[JournalEntry]: Pending entries in chronological order.
        """
        return [e for e in self.entries if e.status == "PENDING"]

    def get_committed_transactions(
        self, since: Optional[datetime] = None,
    ) -> List[JournalEntry]:
        """
        Return COMMITTED transactions, optionally filtered by time.

        Args:
            since (datetime | None): If provided, only return entries
                committed after this timestamp.

        Returns:
            list[JournalEntry]: Matching committed entries.
        """
        committed = [e for e in self.entries if e.status == "COMMITTED"]
        if since is not None:
            committed = [
                e for e in committed
                if e.commit_timestamp and e.commit_timestamp >= since
            ]
        return committed

    # ------------------------------------------------------------------ #
    #  Persistence
    # ------------------------------------------------------------------ #

    def save_journal(self) -> bool:
        """
        Persist the journal to disk as a JSON file.

        Creates parent directories if they do not exist.

        Returns:
            bool: True on success, False on I/O error.
        """
        try:
            directory = os.path.dirname(self.journal_file)
            if directory:
                os.makedirs(directory, exist_ok=True)

            data = [entry.to_dict() for entry in self.entries]
            with open(self.journal_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(
                "Journal saved (%d entries) to %s",
                len(self.entries), self.journal_file,
            )
            return True

        except (OSError, TypeError) as exc:
            logger.error("Failed to save journal: %s", exc)
            return False

    def load_journal(self) -> bool:
        """
        Load journal entries from the on-disk file.

        Returns:
            bool: True on success, False if the file does not exist
                or is corrupt.
        """
        if not os.path.exists(self.journal_file):
            return False

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.entries = [JournalEntry.from_dict(d) for d in data]
            logger.info(
                "Journal loaded: %d entries from %s",
                len(self.entries), self.journal_file,
            )
            return True

        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to load journal: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    #  Maintenance
    # ------------------------------------------------------------------ #

    def checkpoint(self) -> bool:
        """
        Prune old COMMITTED entries to keep the journal lean.

        - All PENDING entries are always kept (needed for recovery).
        - ABORTED entries are removed.
        - Only the most recent *max_entries* COMMITTED entries are
          retained.

        The pruned journal is saved to disk.

        Returns:
            bool: True if the checkpoint succeeded.
        """
        pending = [e for e in self.entries if e.status == "PENDING"]
        committed = [e for e in self.entries if e.status == "COMMITTED"]

        # Keep only the most recent committed entries
        if len(committed) > self.max_entries:
            committed = committed[-self.max_entries:]

        self.entries = pending + committed
        # Re-sort by timestamp for consistent ordering
        self.entries.sort(key=lambda e: e.timestamp)

        logger.debug(
            "Checkpoint: %d pending + %d committed kept",
            len(pending), len(committed),
        )
        return self.save_journal()

    def clear_journal(self, keep_uncommitted: bool = True) -> None:
        """
        Clear journal entries.

        Args:
            keep_uncommitted (bool): If True, PENDING entries are
                preserved (use after successful recovery). If False,
                everything is removed.
        """
        if keep_uncommitted:
            self.entries = [
                e for e in self.entries if e.status == "PENDING"
            ]
        else:
            self.entries.clear()

        logger.info(
            "Journal cleared (keep_uncommitted=%s, remaining=%d)",
            keep_uncommitted, len(self.entries),
        )

    # ------------------------------------------------------------------ #
    #  Statistics
    # ------------------------------------------------------------------ #

    def get_statistics(self) -> dict:
        """
        Return summary statistics about the journal.

        Returns:
            dict: Contains:
                - total_entries (int)
                - pending_count (int)
                - committed_count (int)
                - aborted_count (int)
                - oldest_entry_timestamp (str | None)
                - newest_entry_timestamp (str | None)
        """
        pending = sum(1 for e in self.entries if e.status == "PENDING")
        committed = sum(1 for e in self.entries if e.status == "COMMITTED")
        aborted = sum(1 for e in self.entries if e.status == "ABORTED")

        oldest = None
        newest = None
        if self.entries:
            oldest = min(e.timestamp for e in self.entries).isoformat()
            newest = max(e.timestamp for e in self.entries).isoformat()

        return {
            "total_entries": len(self.entries),
            "pending_count": pending,
            "committed_count": committed,
            "aborted_count": aborted,
            "oldest_entry_timestamp": oldest,
            "newest_entry_timestamp": newest,
        }

    # ------------------------------------------------------------------ #
    #  Dunder
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"Journal(entries={stats['total_entries']}, "
            f"pending={stats['pending_count']}, "
            f"committed={stats['committed_count']})"
        )
