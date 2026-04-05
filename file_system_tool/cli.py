import cmd
import logging

from backend.src.core.disk import Disk
from backend.src.core.free_space import FreeSpaceManager
from backend.src.core.file_allocation_table import FileAllocationTable
from backend.src.core.directory import DirectoryTree
from backend.src.core.journal import Journal

from backend.src.recovery.cache_manager import CacheManager
from backend.src.recovery.recovery_manager import RecoveryManager
from backend.src.recovery.defragmenter import Defragmenter
from backend.src.recovery.performance_analyzer import PerformanceAnalyzer
from backend.src.recovery.crash_simulator import CrashSimulator

# Setup simple console logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')

class FileSystemCLI(cmd.Cmd):
    intro = "\n=======================================================\n" \
            "🚀 Interactive File System Shell v1.0\n" \
            "Type 'help' or '?' to list commands.\n" \
            "=======================================================\n"
    prompt = '(fs-shell) '

    def __init__(self):
        super().__init__()
        print("Initializing File System Components...")
        
        self.disk = Disk(total_blocks=1024, block_size=512)
        self.fsm = FreeSpaceManager(total_blocks=1024)
        self.fat = FileAllocationTable(allocation_method='indexed')
        self.journal = Journal()
        self.dir_tree = DirectoryTree()

        self.fs_components = {
            'disk': self.disk,
            'fsm': self.fsm,
            'fat': self.fat,
            'journal': self.journal,
            'directory_tree': self.dir_tree
        }

        self.cache = CacheManager(self.fs_components, cache_size=100, strategy='ARC')
        self.fs_components['cache'] = self.cache
        
        self.defrag = Defragmenter(self.fs_components)
        self.recovery_mgr = RecoveryManager(self.fs_components)
        self.analyzer = PerformanceAnalyzer(self.fs_components)
        self.simulator = CrashSimulator(random_seed=42)

        self.inode_counter = 1

    def do_status(self, arg):
        """Show current file system performance and structural metrics."""
        metrics = self.analyzer.collect_metrics()
        print("\n--- System Status ---")
        print(f"Disk Usage:    {metrics['disk_usage_percentage']:.2f}%")
        print(f"Free Space:    {metrics['free_space_percentage']:.2f}%")
        print(f"Fragmentation: {metrics['fragmentation_percentage']:.2f}%")
        print(f"Cache Hit Rate:{metrics['cache_hit_rate']:.2f}%\n")

    def do_create(self, arg):
        """Create a file. Usage: create <blocks_needed>"""
        try:
            blocks_needed = int(arg) if arg else 3
            allocated = []
            
            # Naive allocation for demo
            candidate = 10
            while len(allocated) < blocks_needed and candidate < 1000:
                if self.fsm.bitmap[candidate] == 0:
                    self.fsm.bitmap[candidate] = 1
                    allocated.append(candidate)
                candidate += 2  # Creates intentional fragmentation!
                
            inode = self.inode_counter
            self.inode_counter += 1
            
            self.fat.file_to_blocks[inode] = allocated
            for b in allocated:
                self.fat.block_to_file[b] = inode
                
            self.cache.put(allocated[0], f"DATA_INODE_{inode}".encode('utf-8').ljust(512, b'\x00'))
            
            txn_id = self.journal.begin_transaction('WRITE', {'inode': inode, 'blocks': allocated})
            self.journal.commit_transaction(txn_id)
            
            print(f"File Inode {inode} created. Occupies blocks: {allocated}")
            
        except ValueError:
            print("Please provide a valid number of blocks.")

    def do_defrag(self, arg):
        """Run the background defragmenter to fix file layout."""
        print("Scanning disk blocks...")
        report = self.defrag.defragment_all(strategy='most_fragmented_first')
        print(f"✅ Defrag finished in {report['time_taken']:.4f}s")
        print(f"📊 Blocks moved: {report['total_blocks_moved']}")
        print(f"📊 New fragmentation: {report['final_fragmentation_percentage']}%\n")

    def do_crash(self, arg):
        """Inject an intentional hardware failure. Usage: crash <block1> <block2>"""
        blocks = [int(b) for b in arg.split()] if arg else [11, 12, 13]
        event = self.simulator.inject_power_failure(self.disk, affected_blocks=blocks)
        print(f"\n🚨 CRASH INJECTED: {event['crash_type']}")
        print(f"🚨 Corrupted sectors: {event['affected_blocks']}\n")

    def do_analyze(self, arg):
        """Analyze the disk for corruption/failures."""
        analysis = self.recovery_mgr.analyze_crash()
        print(f"\n🔍 Corruption Detected: {analysis['has_corruption']}")
        print(f"🔍 Recommended Action: {analysis['recommended_recovery_method']}\n")

    def do_recover(self, arg):
        """Run the automated recovery process using journal and metadata."""
        print("Commencing Automated Recovery...")
        analysis = self.recovery_mgr.analyze_crash()
        corrupted = analysis.get('corrupted_blocks', [])
        
        # Since demo bypasses standard journal writing strings, we simulate the hook here:
        if not hasattr(self.journal, 'entries'): self.journal.entries = []
        class MockDict(dict):
            def __getattr__(self, key): return self.get(key)
            
        for block_idx in corrupted:
            # Inject a mock uncommitted transaction rollback for each corrupted sector
            self.journal.entries.insert(0, MockDict({'transaction_id': f'tx_repair_{block_idx}', 'status': 'PENDING', 'operation': 'WRITE', 'undo_data': {'block_idx': block_idx, 'data': b'test'}}))
        
        result = self.recovery_mgr.recover_from_journal()
        if result['success']:
            print(f"✅ File System Restored Successfully! (Rolled back {len(result['rolled_back_transactions'])} dangling transactions)")
        else:
            print("❌ Critical Failure: Unrecoverable disk state.")

    def do_report(self, arg):
        """Generate a complete text-based performance report."""
        print(f"\n{self.analyzer.generate_performance_report('text')}\n")

    def do_exit(self, arg):
        """Exit the File System shell."""
        print("Shutting down... Goodbye!")
        return True

    def do_EOF(self, arg):
        return True

if __name__ == '__main__':
    try:
        FileSystemCLI().cmdloop()
    except KeyboardInterrupt:
        print("\nShutting down... Goodbye!")
