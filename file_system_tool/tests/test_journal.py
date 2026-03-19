"""Tests for the Journal class."""

import pytest
from src.core.journal import Journal, JournalEntry, JournalEntryType, JournalEntryStatus


class TestJournalEntry:
    """Test suite for JournalEntry."""

    def test_entry_creation(self):
        entry = JournalEntry(JournalEntryType.CREATE, "Create file test.txt")
        assert entry.entry_type == JournalEntryType.CREATE
        assert entry.status == JournalEntryStatus.PENDING

    def test_commit(self):
        entry = JournalEntry(JournalEntryType.WRITE, "Write data")
        entry.commit()
        assert entry.status == JournalEntryStatus.COMMITTED

    def test_rollback(self):
        entry = JournalEntry(JournalEntryType.DELETE, "Delete file")
        entry.rollback()
        assert entry.status == JournalEntryStatus.ROLLED_BACK

    def test_metadata(self):
        meta = {"filename": "test.txt", "blocks": [1, 2, 3]}
        entry = JournalEntry(JournalEntryType.CREATE, "Create file", metadata=meta)
        assert entry.metadata["filename"] == "test.txt"


class TestJournal:
    """Test suite for Journal."""

    def test_log_entry(self):
        journal = Journal()
        entry = journal.log(JournalEntryType.CREATE, "Create file")
        assert len(journal) == 1
        assert entry.status == JournalEntryStatus.PENDING

    def test_commit_entry(self):
        journal = Journal()
        entry = journal.log(JournalEntryType.WRITE, "Write data")
        assert journal.commit(entry.entry_id) is True

    def test_rollback_entry(self):
        journal = Journal()
        entry = journal.log(JournalEntryType.DELETE, "Delete file")
        assert journal.rollback(entry.entry_id) is True

    def test_pending_entries(self):
        journal = Journal()
        journal.log(JournalEntryType.CREATE, "Create 1")
        e2 = journal.log(JournalEntryType.CREATE, "Create 2")
        journal.commit(e2.entry_id)
        pending = journal.get_pending_entries()
        assert len(pending) == 1

    def test_checkpoint(self):
        journal = Journal()
        journal.log(JournalEntryType.CREATE, "Create 1")
        journal.log(JournalEntryType.CREATE, "Create 2")
        cp = journal.create_checkpoint()
        assert cp == 1
        assert len(journal.get_pending_entries()) == 0

    def test_max_entries_trimming(self):
        journal = Journal(max_entries=5)
        for i in range(10):
            journal.log(JournalEntryType.WRITE, f"Write {i}")
        assert len(journal) == 5

    def test_clear(self):
        journal = Journal()
        journal.log(JournalEntryType.CREATE, "Create 1")
        journal.clear()
        assert len(journal) == 0

    def test_commit_nonexistent(self):
        journal = Journal()
        assert journal.commit(999) is False

    def test_rollback_nonexistent(self):
        journal = Journal()
        assert journal.rollback(999) is False
