import sys
import os

# Add project root to path so we can import from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, project_root)

from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime

from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.directory import DirectoryTree
from src.core.file_allocation_table import FileAllocationTable
from src.core.journal import Journal
from src.recovery.crash_simulator import CrashSimulator
from src.recovery.recovery_manager import RecoveryManager
from src.recovery.defragmenter import Defragmenter
from src.recovery.cache_manager import CacheManager
from src.recovery.performance_analyzer import PerformanceAnalyzer


@dataclass
class AppState:
    """Application state holding file system components"""
    disk: Disk = None
    fsm: FreeSpaceManager = None
    directory_tree: DirectoryTree = None
    fat: FileAllocationTable = None
    journal: Journal = None
    crash_simulator: CrashSimulator = None
    recovery_manager: RecoveryManager = None
    defragmenter: Defragmenter = None
    cache_manager: CacheManager = None
    performance_analyzer: PerformanceAnalyzer = None

    # WebSocket connections
    websocket_connections: List = field(default_factory=list)

    def initialize_filesystem(self, total_blocks: int = 1000, block_size: int = 4096):
        """Initialize all file system components"""
        self.disk = Disk(total_blocks=total_blocks, block_size=block_size)
        self.fsm = FreeSpaceManager(total_blocks=total_blocks)
        self.directory_tree = DirectoryTree()
        self.fat = FileAllocationTable(allocation_method='indexed')
        self.journal = Journal()

        # Recovery and optimization components
        self.crash_simulator = CrashSimulator()

        components = {
            'disk': self.disk,
            'fsm': self.fsm,
            'directory_tree': self.directory_tree,
            'fat': self.fat,
            'journal': self.journal
        }

        self.recovery_manager = RecoveryManager(components)
        self.defragmenter = Defragmenter(components)
        self.cache_manager = CacheManager(self.disk, cache_size=100, strategy='LRU')
        self.performance_analyzer = PerformanceAnalyzer(components)

    def get_components(self) -> Dict[str, Any]:
        """Return all components as dict"""
        return {
            'disk': self.disk,
            'fsm': self.fsm,
            'directory_tree': self.directory_tree,
            'fat': self.fat,
            'journal': self.journal,
            'crash_simulator': self.crash_simulator,
            'recovery_manager': self.recovery_manager,
            'defragmenter': self.defragmenter,
            'cache_manager': self.cache_manager,
            'performance_analyzer': self.performance_analyzer
        }

    async def broadcast(self, message: dict):
        """Broadcast message to all WebSocket connections"""
        for connection in self.websocket_connections:
            try:
                await connection.send_json(message)
            except:
                self.websocket_connections.remove(connection)
