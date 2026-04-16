"""
state.py - Global file system state management.

Provides a shared FileSystemState class that maintains the singleton instances
of all file system components (disk, directory tree, FAT, FSM, journal, etc.)
for use across all API routes.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock

# Handle imports for both module and direct execution
try:
    from core.disk import Disk
    from core.directory import DirectoryTree
    from core.file_allocation_table import FileAllocationTable
    from core.free_space import FreeSpaceManager
    from core.journal import Journal
    from core.inode import Inode
    from utils.constants import FileSystemConfig

    from recovery.recovery_manager import RecoveryManager
    from recovery.defragmenter import Defragmenter
    from recovery.cache_manager import CacheManager
    from recovery.crash_simulator import CrashSimulator
    from recovery.performance_analyzer import PerformanceAnalyzer
except ImportError:
    # Relative imports when running as part of package
    from core.disk import Disk
    from core.directory import DirectoryTree
    from core.file_allocation_table import FileAllocationTable
    from core.free_space import FreeSpaceManager
    from core.journal import Journal
    from core.inode import Inode
    from utils.constants import FileSystemConfig

    from recovery.recovery_manager import RecoveryManager
    from recovery.defragmenter import Defragmenter
    from recovery.cache_manager import CacheManager
    from recovery.crash_simulator import CrashSimulator
    from recovery.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class FileSystemState:
    """
    Singleton container for all file system components.

    Maintains references to all initialized file system modules
    and provides thread-safe access for API route handlers.

    Attributes:
        disk (Disk): Simulated disk storage.
        directory_tree (DirectoryTree): Directory hierarchy.
        fat (FileAllocationTable): File allocation table.
        fsm (FreeSpaceManager): Free space bitmap manager.
        journal (Journal): Transaction journal.
        inode_counter (int): Counter for generating unique inode numbers.
        recovery_manager (RecoveryManager): Recovery operations handler.
        defragmenter (Defragmenter): Defragmentation handler.
        cache_manager (CacheManager): Block caching handler.
        crash_simulator (CrashSimulator): Crash simulation handler.
        performance_analyzer (PerformanceAnalyzer): Performance monitoring.
    """

    _instance: Optional["FileSystemState"] = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        total_blocks: int = 1024,
        block_size: int = 4096,
        allocation_method: str = "indexed",
        allocation_strategy: str = "first_fit",
        journal_file: str = "data/journal.log",
    ):
        """
        Initialize file system state (only runs once).

        Args:
            total_blocks (int): Total blocks for the disk.
            block_size (int): Bytes per block.
            allocation_method (str): FAT allocation method ('contiguous', 'linked', 'indexed').
            allocation_strategy (str): FSM strategy ('first_fit', 'best_fit', 'worst_fit').
            journal_file (str): Path for journal persistence.
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("Initializing FileSystemState...")

            # Core components
            self.disk = Disk(total_blocks=total_blocks, block_size=block_size)
            self.directory_tree = DirectoryTree()
            self.fat = FileAllocationTable(allocation_method=allocation_method)
            self.fsm = FreeSpaceManager(
                total_blocks=total_blocks, strategy=allocation_strategy
            )
            # Reserve blocks 0-3 for boot sector, super block, journal, etc.
            self.fsm.allocate_blocks(4, contiguous=True)
            self.journal = Journal(journal_file=journal_file)

            # Inode counter for generating unique inode numbers
            self.inode_counter = 1

            # Recovery components
            self.recovery_manager = RecoveryManager(self.to_dict())
            self.defragmenter = Defragmenter(self.to_dict())
            self.cache_manager = CacheManager(self.disk)
            self.crash_simulator = CrashSimulator()
            self.performance_analyzer = PerformanceAnalyzer(self.to_dict())

            self._initialized = True
            logger.info("FileSystemState initialized successfully")

    def to_dict(self) -> Dict[str, Any]:
        """
        Return all components as a dictionary for recovery modules.

        Returns:
            dict: Mapping of component names to instances.
        """
        return {
            "disk": self.disk,
            "directory_tree": self.directory_tree,
            "fat": self.fat,
            "fsm": self.fsm,
            "journal": self.journal,
        }

    def get_next_inode_number(self) -> int:
        """
        Generate and return the next unique inode number.

        Returns:
            int: Unique inode number.
        """
        with self._lock:
            inode_num = self.inode_counter
            self.inode_counter += 1
            return inode_num

    def refresh_recovery_components(self):
        """
        Refresh recovery component references after state changes.

        Call this after significant state mutations to ensure recovery
        modules have updated references.
        """
        components = self.to_dict()
        self.recovery_manager = RecoveryManager(components)
        self.defragmenter = Defragmenter(components)
        self.performance_analyzer = PerformanceAnalyzer(components)

    def reset(self):
        """
        Reset all file system state to initial conditions.

        WARNING: This destroys all data and cannot be undone.
        """
        with self._lock:
            total_blocks = self.disk.total_blocks
            block_size = self.disk.block_size
            allocation_method = self.fat.allocation_method
            strategy = self.fsm.allocation_strategy
            journal_file = self.journal.journal_file

            self.disk.format_disk()
            self.directory_tree = DirectoryTree()
            self.fat = FileAllocationTable(allocation_method=allocation_method)
            self.fsm = FreeSpaceManager(
                total_blocks=total_blocks, strategy=strategy
            )
            # Reserve blocks 0-3
            self.fsm.allocate_blocks(4, contiguous=True)
            self.journal.clear_journal(keep_uncommitted=False)

            self.inode_counter = 1

            self.recovery_manager = RecoveryManager(self.to_dict())
            self.defragmenter = Defragmenter(self.to_dict())
            self.cache_manager = CacheManager(self.disk)
            self.crash_simulator = CrashSimulator()
            self.performance_analyzer = PerformanceAnalyzer(self.to_dict())

            logger.info("FileSystemState reset complete")

    def factory_reset(self) -> Dict[str, Any]:
        """
        Perform a factory reset by deleting persisted artifacts and rebuilding
        a pristine in-memory file system state.

        Returns:
            dict: Metadata about deleted persistence files.
        """
        with self._lock:
            total_blocks = self.disk.total_blocks
            block_size = self.disk.block_size
            allocation_method = self.fat.allocation_method
            allocation_strategy = self.fsm.allocation_strategy
            journal_file = self.journal.journal_file

            backend_root = Path(__file__).resolve().parents[1]
            data_dir = backend_root / "data"

            deleted_files = []
            candidate_paths = set()

            configured_journal = Path(journal_file)
            if not configured_journal.is_absolute():
                configured_journal = backend_root / configured_journal
            candidate_paths.add(configured_journal)
            candidate_paths.add(data_dir / "journal.log")
            candidate_paths.add(data_dir / "disk.img")

            if data_dir.exists():
                for pattern in ("*.img", "*.bin", "*.disk", "*.pkl", "*.pickle"):
                    for image_path in data_dir.glob(pattern):
                        candidate_paths.add(image_path)

            for file_path in candidate_paths:
                try:
                    if file_path.exists() and file_path.is_file():
                        os.remove(file_path)
                        deleted_files.append(str(file_path))
                except OSError as exc:
                    logger.warning("Failed to delete persistence file %s: %s", file_path, exc)

            # Recreate all core modules with a fresh state.
            self.disk = Disk(total_blocks=total_blocks, block_size=block_size)
            self.directory_tree = DirectoryTree()
            self.fat = FileAllocationTable(allocation_method=allocation_method)
            self.fsm = FreeSpaceManager(
                total_blocks=total_blocks, strategy=allocation_strategy
            )
            self.fsm.allocate_blocks(4, contiguous=True)
            self.journal = Journal(journal_file=journal_file)

            self.inode_counter = 1

            components = self.to_dict()
            self.recovery_manager = RecoveryManager(components)
            self.defragmenter = Defragmenter(components)
            self.cache_manager = CacheManager(self.disk)
            self.crash_simulator = CrashSimulator()
            self.performance_analyzer = PerformanceAnalyzer(components)

            logger.info("Factory reset complete. Deleted %d persistence files", len(deleted_files))
            return {"deleted_files": deleted_files}


# Global state instance
fs_state = FileSystemState()


def get_state() -> FileSystemState:
    """
    Get the global FileSystemState instance.

    Returns:
        FileSystemState: The singleton state instance.
    """
    return fs_state
