"""Tests for the JournalEntry and Journal classes."""

import os
import pytest
from backend.src.core.journal import Journal, JournalEntry


class TestJournalEntry:
    """Test suite for JournalEntry."""

    def test_entry_creation(self):
        entry = JournalEntry("CREATE", {"filename": "test.txt"})
        assert entry.operation == "CREATE"
        assert entry.status == "PENDING"

    def test_commit(self):
        entry = JournalEntry("WRITE", {"data": "hello"})
        entry.commit()
        assert entry.status == "COMMITTED"
        assert entry.commit_timestamp is not None

    def test_abort(self):
        entry = JournalEntry("DELETE", {"filename": "file.txt"})
        entry.abort()
        assert entry.status == "ABORTED"

    def test_metadata(self):
        meta = {"filename": "test.txt", "blocks": [1, 2, 3]}
        entry = JournalEntry("CREATE", meta)
        assert entry.metadata["filename"] == "test.txt"

    def test_serialization(self):
        entry = JournalEntry("WRITE", {"data": "test"})
        data = entry.to_dict()
        restored = JournalEntry.from_dict(data)
        assert restored.operation == "WRITE"
        assert restored.status == "PENDING"


class TestJournal:
    """Test suite for Journal."""

    @pytest.fixture(autouse=True)
    def use_tmp_journal(self, tmp_path):
        """Use a temporary journal file for each test."""
        self.journal_file = str(tmp_path / "test_journal.log")

    def test_begin_transaction(self):
        journal = Journal(journal_file=self.journal_file)
        tid = journal.begin_transaction("CREATE", {"filename": "file.txt"})
        assert len(journal) == 1
        assert tid is not None

    def test_commit_transaction(self):
        journal = Journal(journal_file=self.journal_file)
        tid = journal.begin_transaction("WRITE", {"data": "hello"})
        assert journal.commit_transaction(tid) is True

    def test_abort_transaction(self):
        journal = Journal(journal_file=self.journal_file)
        tid = journal.begin_transaction("DELETE", {"filename": "file.txt"})
        assert journal.abort_transaction(tid) is True

    def test_uncommitted_transactions(self):
        journal = Journal(journal_file=self.journal_file)
        journal.begin_transaction("CREATE", {"f": "1"})
        tid2 = journal.begin_transaction("CREATE", {"f": "2"})
        journal.commit_transaction(tid2)
        pending = journal.get_uncommitted_transactions()
        assert len(pending) == 1

    def test_checkpoint(self):
        journal = Journal(journal_file=self.journal_file)
        tid1 = journal.begin_transaction("CREATE", {"f": "1"})
        tid2 = journal.begin_transaction("CREATE", {"f": "2"})
        journal.commit_transaction(tid1)
        journal.commit_transaction(tid2)
        result = journal.checkpoint()
        assert result is True

    def test_clear(self):
        journal = Journal(journal_file=self.journal_file)
        journal.begin_transaction("CREATE", {"f": "1"})
        journal.clear_journal(keep_uncommitted=False)
        assert len(journal) == 0

    def test_commit_nonexistent(self):
        journal = Journal(journal_file=self.journal_file)
        assert journal.commit_transaction("nonexistent-id") is False

    def test_abort_nonexistent(self):
        journal = Journal(journal_file=self.journal_file)
        assert journal.abort_transaction("nonexistent-id") is False

    def test_statistics(self):
        journal = Journal(journal_file=self.journal_file)
        journal.begin_transaction("CREATE", {"f": "1"})
        stats = journal.get_statistics()
        assert stats["total_entries"] == 1
        assert stats["pending_count"] == 1
