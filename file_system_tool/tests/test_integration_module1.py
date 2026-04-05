"""
test_integration_module1.py - Comprehensive integration tests.

Exercises all six core modules together:
  Disk · FreeSpaceManager · Inode · DirectoryTree ·
  FileAllocationTable · Journal

7 test suites:
  1. Complete file creation flow
  2. File deletion flow
  3. Disk persistence
  4. Journal recovery simulation
  5. Free space management & fragmentation
  6. Directory operations
  7. File allocation methods
"""

import os
import tempfile

import pytest

from backend.src.core.disk import Disk
from backend.src.core.free_space import FreeSpaceManager
from backend.src.core.inode import Inode
from backend.src.core.directory import DirectoryTree
from backend.src.core.file_allocation_table import FileAllocationTable
from backend.src.core.journal import Journal


# ===================================================================== #
#  Helpers & fixtures
# ===================================================================== #

NUM_BLOCKS = 1000
BLOCK_SIZE = 4096


def create_test_disk() -> Disk:
    """Return a small Disk instance for testing."""
    return Disk(total_blocks=NUM_BLOCKS, block_size=BLOCK_SIZE)


def create_test_file_system() -> dict:
    """Return a dict with all file-system components wired up."""
    return {
        "disk": create_test_disk(),
        "fsm": FreeSpaceManager(total_blocks=NUM_BLOCKS, strategy="first_fit"),
        "fat": FileAllocationTable(allocation_method="indexed"),
        "tree": DirectoryTree(),
        "journal": Journal(
            journal_file=os.path.join(tempfile.mkdtemp(), "journal.log")
        ),
    }


@pytest.fixture
def fs():
    """Pytest fixture providing a clean file-system environment."""
    return create_test_file_system()


@pytest.fixture
def tmp_path_str():
    """Return a temporary directory path as a plain string."""
    d = tempfile.mkdtemp()
    yield d
    # Cleanup
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    os.rmdir(d)


# ===================================================================== #
#  Suite 1 — Complete File Creation Flow
# ===================================================================== #

class TestFileCreationFlow:
    """End-to-end file creation: allocate → inode → directory → FAT → journal."""

    def test_complete_file_creation(self, fs):
        disk = fs["disk"]
        fsm = fs["fsm"]
        fat = fs["fat"]
        tree = fs["tree"]
        journal = fs["journal"]

        # 1. Allocate 10 contiguous blocks
        blocks = fsm.allocate_blocks(10, contiguous=True)
        assert blocks is not None
        assert len(blocks) == 10

        # 2. Create inode with allocated blocks
        inode = Inode(inode_number=1, file_type="file", size=10 * BLOCK_SIZE)
        for b in blocks:
            assert inode.add_block_pointer(b) is True

        # 3. Add file to directory tree
        assert tree.create_file("/test.txt", inode) is True

        # 4. Record allocation in FAT
        assert fat.allocate(1, blocks) is True

        # 5. Log transaction in journal
        txn_id = journal.begin_transaction("CREATE", {
            "path": "/test.txt",
            "inode_number": 1,
            "blocks": blocks,
        })
        assert journal.commit_transaction(txn_id) is True

        # --- Verify all components ---
        assert fsm.get_allocated_count() == 10
        assert fsm.get_free_count() == NUM_BLOCKS - 10
        assert fat.get_file_blocks(1) == blocks
        assert fat.get_block_owner(blocks[0]) == 1
        resolved = tree.resolve_path("/test.txt")
        assert resolved is not None
        assert resolved.inode.inode_number == 1
        assert journal.get_statistics()["committed_count"] == 1

    def test_create_multiple_files(self, fs):
        fsm = fs["fsm"]
        fat = fs["fat"]
        tree = fs["tree"]

        for i in range(5):
            blocks = fsm.allocate_blocks(3, contiguous=True)
            assert blocks is not None
            inode = Inode(inode_number=i + 1, file_type="file",
                          size=3 * BLOCK_SIZE)
            for b in blocks:
                inode.add_block_pointer(b)
            assert tree.create_file(f"/file_{i}.txt", inode) is True
            assert fat.allocate(i + 1, blocks) is True

        assert fsm.get_allocated_count() == 15
        assert len(fat.file_to_blocks) == 5
        listing = tree.list_directory("/")
        assert len(listing) == 5

    def test_create_file_in_nested_directory(self, fs):
        tree = fs["tree"]
        fsm = fs["fsm"]
        fat = fs["fat"]

        assert tree.create_directory("/home/user/docs") is True

        blocks = fsm.allocate_blocks(2, contiguous=True)
        inode = Inode(inode_number=10, file_type="file",
                      size=2 * BLOCK_SIZE)
        for b in blocks:
            inode.add_block_pointer(b)

        assert tree.create_file("/home/user/docs/report.txt", inode) is True
        assert fat.allocate(10, blocks) is True

        node = tree.resolve_path("/home/user/docs/report.txt")
        assert node is not None
        assert node.is_directory is False

    def test_duplicate_file_creation_fails(self, fs):
        tree = fs["tree"]
        inode1 = Inode(inode_number=1, file_type="file")
        inode2 = Inode(inode_number=2, file_type="file")

        assert tree.create_file("/dup.txt", inode1) is True
        assert tree.create_file("/dup.txt", inode2) is False


# ===================================================================== #
#  Suite 2 — File Deletion Flow
# ===================================================================== #

class TestFileDeletionFlow:
    """End-to-end file deletion with complete cleanup verification."""

    def test_complete_file_deletion(self, fs):
        disk = fs["disk"]
        fsm = fs["fsm"]
        fat = fs["fat"]
        tree = fs["tree"]
        journal = fs["journal"]

        # Setup: create a file
        blocks = fsm.allocate_blocks(5, contiguous=True)
        inode = Inode(inode_number=42, file_type="file",
                      size=5 * BLOCK_SIZE)
        for b in blocks:
            inode.add_block_pointer(b)
            disk.write_block(b, b"data_" + bytes([b]))
        tree.create_file("/to_delete.txt", inode)
        fat.allocate(42, blocks)

        # Delete flow
        node = tree.resolve_path("/to_delete.txt")
        assert node is not None

        file_blocks = fat.get_file_blocks(42)
        assert file_blocks == blocks

        # 1. Remove from directory tree
        assert tree.delete("/to_delete.txt") is True

        # 2. Deallocate blocks in free space manager
        assert fsm.deallocate_blocks(file_blocks) is True

        # 3. Remove from FAT
        freed = fat.deallocate(42)
        assert freed == blocks

        # 4. Log deletion in journal
        txn_id = journal.begin_transaction("DELETE", {
            "path": "/to_delete.txt",
            "inode_number": 42,
            "blocks": blocks,
        })
        journal.commit_transaction(txn_id)

        # --- Verify cleanup ---
        assert tree.resolve_path("/to_delete.txt") is None
        assert fsm.get_free_count() == NUM_BLOCKS
        assert fat.get_file_blocks(42) == []
        assert fat.get_block_owner(blocks[0]) is None

    def test_delete_nonexistent_file(self, fs):
        assert fs["tree"].delete("/no_such_file.txt") is False

    def test_delete_nonempty_dir_without_recursive(self, fs):
        tree = fs["tree"]
        tree.create_directory("/mydir")
        inode = Inode(inode_number=1, file_type="file")
        tree.create_file("/mydir/file.txt", inode)
        assert tree.delete("/mydir", recursive=False) is False

    def test_delete_nonempty_dir_with_recursive(self, fs):
        tree = fs["tree"]
        tree.create_directory("/mydir")
        inode = Inode(inode_number=1, file_type="file")
        tree.create_file("/mydir/file.txt", inode)
        assert tree.delete("/mydir", recursive=True) is True
        assert tree.resolve_path("/mydir") is None


# ===================================================================== #
#  Suite 3 — Disk Persistence
# ===================================================================== #

class TestDiskPersistence:
    """Save disk state → load in new instance → verify data."""

    def test_save_and_load(self, tmp_path_str):
        filepath = os.path.join(tmp_path_str, "disk.img")
        disk = create_test_disk()

        disk.write_block(0, b"hello, world!")
        disk.write_block(999, b"last block")
        disk.read_block(0)

        assert disk.save_to_file(filepath) is True

        loaded = Disk.load_from_file(filepath)
        assert loaded.total_blocks == disk.total_blocks
        assert loaded.block_size == disk.block_size
        assert loaded.blocks[0] == b"hello, world!"
        assert loaded.blocks[999] == b"last block"
        assert loaded.metadata["total_writes"] == 2
        assert loaded.metadata["total_reads"] == 1

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            Disk.load_from_file("/nonexistent/path/disk.img")

    def test_block_access_times_persist(self, tmp_path_str):
        filepath = os.path.join(tmp_path_str, "disk2.img")
        disk = create_test_disk()
        disk.write_block(5, b"data")

        assert 5 in disk.block_access_times
        disk.save_to_file(filepath)

        loaded = Disk.load_from_file(filepath)
        assert 5 in loaded.block_access_times

    def test_format_then_save_load(self, tmp_path_str):
        filepath = os.path.join(tmp_path_str, "disk3.img")
        disk = create_test_disk()
        disk.write_block(0, b"old data")
        disk.format_disk()
        assert disk.blocks[0] is None
        disk.save_to_file(filepath)

        loaded = Disk.load_from_file(filepath)
        assert loaded.blocks[0] is None
        assert loaded.metadata["total_writes"] == 0


# ===================================================================== #
#  Suite 4 — Journal Recovery Simulation
# ===================================================================== #

class TestJournalRecovery:
    """Simulate crash and verify uncommitted transaction detection."""

    def test_uncommitted_detected_after_crash(self):
        journal_dir = tempfile.mkdtemp()
        journal_path = os.path.join(journal_dir, "journal.log")

        # --- Phase 1: begin transaction, save, "crash" (no commit) ---
        journal1 = Journal(journal_file=journal_path)
        txn_id = journal1.begin_transaction("WRITE", {
            "inode_number": 7,
            "blocks": [10, 11, 12],
        })
        journal1.add_redo_data(txn_id, {"blocks_data": "b64encoded…"})
        journal1.add_undo_data(txn_id, {"old_blocks_data": "b64old…"})
        journal1.save_journal()
        # Simulate crash — do NOT commit

        # --- Phase 2: new process loads journal for recovery ---
        journal2 = Journal(journal_file=journal_path)
        uncommitted = journal2.get_uncommitted_transactions()
        assert len(uncommitted) == 1
        assert uncommitted[0].transaction_id == txn_id
        assert uncommitted[0].status == "PENDING"
        assert uncommitted[0].undo_data.get("old_blocks_data") == "b64old…"

    def test_committed_not_flagged_as_pending(self):
        journal_dir = tempfile.mkdtemp()
        journal_path = os.path.join(journal_dir, "journal.log")

        journal = Journal(journal_file=journal_path)
        txn_id = journal.begin_transaction("CREATE", {"path": "/ok.txt"})
        journal.commit_transaction(txn_id)

        journal2 = Journal(journal_file=journal_path)
        assert len(journal2.get_uncommitted_transactions()) == 0
        assert len(journal2.get_committed_transactions()) == 1

    def test_abort_transaction(self):
        journal_dir = tempfile.mkdtemp()
        journal = Journal(
            journal_file=os.path.join(journal_dir, "j.log")
        )
        txn = journal.begin_transaction("DELETE", {"path": "/x.txt"})
        assert journal.abort_transaction(txn) is True

        stats = journal.get_statistics()
        assert stats["aborted_count"] == 1
        assert stats["pending_count"] == 0

    def test_checkpoint_prunes_old_entries(self):
        journal_dir = tempfile.mkdtemp()
        journal = Journal(
            journal_file=os.path.join(journal_dir, "j.log"),
            max_entries=5,
        )

        # Create 10 committed transactions
        for i in range(10):
            txn = journal.begin_transaction("WRITE", {"i": i})
            journal.commit_transaction(txn)

        assert len(journal.entries) == 10
        journal.checkpoint()
        assert len(journal.entries) <= 5

    def test_clear_keeps_uncommitted(self):
        journal_dir = tempfile.mkdtemp()
        journal = Journal(
            journal_file=os.path.join(journal_dir, "j.log")
        )
        txn1 = journal.begin_transaction("CREATE", {})
        journal.commit_transaction(txn1)

        txn2 = journal.begin_transaction("WRITE", {})  # left PENDING

        journal.clear_journal(keep_uncommitted=True)
        assert len(journal.entries) == 1
        assert journal.entries[0].status == "PENDING"


# ===================================================================== #
#  Suite 5 — Free Space Management & Fragmentation
# ===================================================================== #

class TestFreeSpaceManagement:
    """All allocation strategies, fragmentation detection, edge cases."""

    def test_first_fit_allocation(self):
        fsm = FreeSpaceManager(total_blocks=100, strategy="first_fit")
        blocks = fsm.allocate_blocks(10, contiguous=True)
        assert blocks == list(range(0, 10))

    def test_best_fit_allocation(self):
        fsm = FreeSpaceManager(total_blocks=100, strategy="best_fit")
        # Allocate blocks 0-49, then free 10-19 (10 blocks) and 30-49 (20 blocks)
        fsm.allocate_blocks(50, contiguous=True)
        fsm.deallocate_blocks(list(range(10, 20)))  # 10-block hole
        fsm.deallocate_blocks(list(range(30, 50)))   # 20-block hole

        # Best-fit for 8 blocks should pick the 10-block hole (smaller fit)
        blocks = fsm.allocate_blocks(8, contiguous=True)
        assert blocks is not None
        assert blocks[0] == 10  # picked the smaller hole

    def test_worst_fit_allocation(self):
        fsm = FreeSpaceManager(total_blocks=100, strategy="worst_fit")
        fsm.allocate_blocks(50, contiguous=True)
        fsm.deallocate_blocks(list(range(10, 20)))  # 10-block hole
        fsm.deallocate_blocks(list(range(30, 50)))   # 20-block hole

        # Worst-fit for 8 blocks should pick the 20-block hole (larger)
        blocks = fsm.allocate_blocks(8, contiguous=True)
        assert blocks is not None
        assert blocks[0] == 30  # picked the larger hole

    def test_scattered_allocation(self):
        fsm = FreeSpaceManager(total_blocks=100, strategy="first_fit")
        # Allocate ALL blocks, then free odd-numbered ones
        # to create a checkerboard fragmentation pattern
        fsm.allocate_blocks(100, contiguous=True)
        fsm.deallocate_blocks(list(range(1, 100, 2)))  # free odd blocks

        # 50 scattered free blocks remain (all odd-numbered)
        assert fsm.get_free_count() == 50

        blocks = fsm.allocate_blocks(10, contiguous=False)
        assert blocks is not None
        assert len(blocks) == 10
        # They should be odd-numbered blocks
        for b in blocks:
            assert b % 2 == 1

    def test_fragmentation_detection(self):
        fsm = FreeSpaceManager(total_blocks=100, strategy="first_fit")
        # Fresh disk: 0 % fragmentation
        assert fsm.get_fragmentation_percentage() == 0.0

        # Allocate blocks 0–9 → one transition at block 10
        fsm.allocate_blocks(10, contiguous=True)
        frag = fsm.get_fragmentation_percentage()
        assert frag > 0.0

    def test_allocation_failure_disk_full(self):
        fsm = FreeSpaceManager(total_blocks=10, strategy="first_fit")
        fsm.allocate_blocks(10, contiguous=True)
        assert fsm.get_free_count() == 0

        # Both contiguous and scattered should fail
        assert fsm.allocate_blocks(1, contiguous=True) is None
        assert fsm.allocate_blocks(1, contiguous=False) is None

    def test_set_allocation_strategy(self):
        fsm = FreeSpaceManager(total_blocks=50, strategy="first_fit")
        assert fsm.set_allocation_strategy("best_fit") is True
        assert fsm.allocation_strategy == "best_fit"
        assert fsm.set_allocation_strategy("invalid") is False

    def test_get_all_free_regions(self):
        fsm = FreeSpaceManager(total_blocks=20, strategy="first_fit")
        fsm.allocate_blocks(5, contiguous=True)        # 0-4 allocated
        fsm.allocate_blocks(3, contiguous=True)         # 5-7 allocated
        fsm.deallocate_blocks(list(range(0, 5)))        # 0-4 free again

        regions = fsm.get_all_free_regions()
        assert len(regions) >= 2  # hole at 0-4 and 8-19
        starts = [r[0] for r in regions]
        assert 0 in starts
        assert 8 in starts

    def test_invalid_deallocation(self):
        fsm = FreeSpaceManager(total_blocks=10, strategy="first_fit")
        # Trying to free an already-free block
        assert fsm.deallocate_blocks([0]) is False

    def test_allocation_map_stats(self):
        fsm = FreeSpaceManager(total_blocks=50, strategy="first_fit")
        fsm.allocate_blocks(20, contiguous=True)
        stats = fsm.get_allocation_map()
        assert stats["total_blocks"] == 50
        assert stats["free_blocks"] == 30
        assert stats["allocated_blocks"] == 20
        assert stats["largest_contiguous_space"] == 30


# ===================================================================== #
#  Suite 6 — Directory Operations
# ===================================================================== #

class TestDirectoryOperations:
    """Path resolution, nested dirs, listing, recursive delete."""

    def test_create_nested_directories(self, fs):
        tree = fs["tree"]
        assert tree.create_directory("/home/user/documents") is True
        assert tree.resolve_path("/home") is not None
        assert tree.resolve_path("/home/user") is not None
        assert tree.resolve_path("/home/user/documents") is not None

    def test_absolute_path_resolution(self, fs):
        tree = fs["tree"]
        tree.create_directory("/a/b/c")
        node = tree.resolve_path("/a/b/c")
        assert node is not None
        assert node.name == "c"
        assert node.get_full_path() == "/a/b/c"

    def test_relative_path_resolution(self, fs):
        tree = fs["tree"]
        tree.create_directory("/home/user")
        tree.change_directory("/home")

        node = tree.resolve_path("user")
        assert node is not None
        assert node.name == "user"

    def test_dot_and_dotdot(self, fs):
        tree = fs["tree"]
        tree.create_directory("/home/user")
        tree.change_directory("/home/user")

        # . stays in current
        assert tree.resolve_path(".").name == "user"
        # .. goes up
        assert tree.resolve_path("..").name == "home"
        # ../.. goes to root
        assert tree.resolve_path("../..").get_full_path() == "/"

    def test_change_directory(self, fs):
        tree = fs["tree"]
        tree.create_directory("/var/log")
        assert tree.change_directory("/var/log") is True
        assert tree.get_current_path() == "/var/log"

    def test_cd_to_file_fails(self, fs):
        tree = fs["tree"]
        inode = Inode(inode_number=1, file_type="file")
        tree.create_file("/readme.txt", inode)
        assert tree.change_directory("/readme.txt") is False

    def test_list_directory(self, fs):
        tree = fs["tree"]
        tree.create_directory("/mydir")
        inode1 = Inode(inode_number=1, file_type="file", size=1024)
        inode2 = Inode(inode_number=2, file_type="file", size=2048)
        tree.create_file("/mydir/a.txt", inode1)
        tree.create_file("/mydir/b.txt", inode2)

        entries = tree.list_directory("/mydir")
        assert len(entries) == 2
        names = [e["name"] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names
        # Entries should be sorted
        assert names == sorted(names)

    def test_find_by_inode(self, fs):
        tree = fs["tree"]
        inode = Inode(inode_number=99, file_type="file")
        tree.create_file("/lookup.txt", inode)
        found = tree.find_by_inode(99)
        assert found is not None
        assert found.name == "lookup.txt"

    def test_tree_structure_output(self, fs):
        tree = fs["tree"]
        tree.create_directory("/home/user")
        inode = Inode(inode_number=1, file_type="file")
        tree.create_file("/home/user/file.txt", inode)
        tree.create_directory("/var")

        output = tree.get_tree_structure()
        assert "/" in output
        assert "home" in output
        assert "file.txt" in output
        assert "var" in output

    def test_resolve_invalid_path(self, fs):
        tree = fs["tree"]
        assert tree.resolve_path("/does/not/exist") is None

    def test_recursive_delete_cleans_inode_map(self, fs):
        tree = fs["tree"]
        tree.create_directory("/project")
        inode1 = Inode(inode_number=10, file_type="file")
        inode2 = Inode(inode_number=11, file_type="file")
        tree.create_file("/project/a.py", inode1)
        tree.create_file("/project/b.py", inode2)

        assert tree.find_by_inode(10) is not None
        assert tree.delete("/project", recursive=True) is True
        assert tree.find_by_inode(10) is None
        assert tree.find_by_inode(11) is None


# ===================================================================== #
#  Suite 7 — File Allocation Methods
# ===================================================================== #

class TestFileAllocationMethods:
    """Contiguous, linked, indexed allocation + fragmentation."""

    def test_contiguous_allocation(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        blocks = list(range(10, 20))
        assert fat.allocate_contiguous(1, blocks) is True
        assert fat.get_file_blocks(1) == blocks
        assert fat.is_fragmented(1) is False

    def test_contiguous_rejects_gaps(self):
        fat = FileAllocationTable(allocation_method="contiguous")
        assert fat.allocate_contiguous(1, [10, 11, 13]) is False

    def test_linked_allocation(self):
        fat = FileAllocationTable(allocation_method="linked")
        blocks = [5, 20, 42, 100]
        assert fat.allocate_linked(1, blocks) is True
        assert fat.get_file_blocks(1) == blocks
        assert fat.is_fragmented(1) is True  # linked is always fragmented

        # Follow the chain
        chain = fat.follow_linked_chain(5)
        assert chain == blocks

    def test_indexed_allocation(self):
        fat = FileAllocationTable(allocation_method="indexed")
        blocks = [3, 7, 15, 22]
        assert fat.allocate_indexed(1, blocks) is True
        assert fat.get_file_blocks(1) == blocks

        # Non-sequential → fragmented
        assert fat.is_fragmented(1) is True

    def test_indexed_sequential_not_fragmented(self):
        fat = FileAllocationTable(allocation_method="indexed")
        blocks = [10, 11, 12, 13]
        fat.allocate_indexed(1, blocks)
        assert fat.is_fragmented(1) is False

    def test_allocate_dispatcher(self):
        fat = FileAllocationTable(allocation_method="indexed")
        assert fat.allocate(1, [0, 1, 2]) is True
        assert fat.get_file_blocks(1) == [0, 1, 2]

    def test_deallocate(self):
        fat = FileAllocationTable(allocation_method="linked")
        fat.allocate(1, [10, 20, 30])
        freed = fat.deallocate(1)
        assert freed == [10, 20, 30]
        assert fat.get_file_blocks(1) == []
        assert fat.get_block_owner(10) is None
        # next_pointers should be cleaned up
        assert 10 not in fat.next_pointers

    def test_block_double_allocation_prevented(self):
        fat = FileAllocationTable(allocation_method="indexed")
        fat.allocate(1, [10, 11, 12])
        assert fat.allocate(2, [12, 13, 14]) is False  # block 12 conflict

    def test_validate_allocation(self):
        fat = FileAllocationTable(allocation_method="linked")
        fat.allocate(1, [5, 10, 15])
        assert fat.validate_allocation(1) is True
        assert fat.validate_allocation(999) is False  # non-existent

    def test_fragmentation_stats(self):
        fat = FileAllocationTable(allocation_method="indexed")
        fat.allocate(1, [0, 1, 2])       # not fragmented
        fat.allocate(2, [5, 10, 20])      # fragmented
        fat.allocate(3, [30, 31, 32])     # not fragmented

        stats = fat.get_fragmentation_stats()
        assert stats["total_files"] == 3
        assert stats["fragmented_files"] == 1
        assert stats["fragmentation_percentage"] == pytest.approx(1 / 3 * 100,
                                                                   rel=0.01)

    def test_get_block_owner(self):
        fat = FileAllocationTable(allocation_method="indexed")
        fat.allocate(42, [100, 101])
        assert fat.get_block_owner(100) == 42
        assert fat.get_block_owner(999) is None
