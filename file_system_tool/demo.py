import time
import logging

from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.file_allocation_table import FileAllocationTable
from src.core.directory import DirectoryTree
from src.core.journal import Journal

from src.recovery.cache_manager import CacheManager
from src.recovery.recovery_manager import RecoveryManager
from src.recovery.defragmenter import Defragmenter
from src.recovery.performance_analyzer import PerformanceAnalyzer
from src.recovery.crash_simulator import CrashSimulator

# Setup simple console logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_demo():
    print("=====================================================")
    print("🚀 INIT: Starting File System Simulator Pipeline")
    print("=====================================================\n")

    # 1. Initialize Core Infrastructure
    disk = Disk(total_blocks=1024, block_size=512)
    fsm = FreeSpaceManager(total_blocks=1024)
    fat = FileAllocationTable(allocation_method='indexed')
    journal = Journal()
    dir_tree = DirectoryTree()

    # Consolidate Components
    fs_components = {
        'disk': disk,
        'fsm': fsm,
        'fat': fat,
        'journal': journal,
        'directory_tree': dir_tree
    }

    # 2. Add Advanced Recovery & Optimization Modules
    cache = CacheManager(fs_components, cache_size=100, strategy='ARC')
    fs_components['cache'] = cache  # Feed cache back into components
    
    defrag = Defragmenter(fs_components)
    recovery_mgr = RecoveryManager(fs_components)
    analyzer = PerformanceAnalyzer(fs_components)
    simulator = CrashSimulator(random_seed=42)

    print("[SUCCESS] All 10 Core & Recovery Modules Initialized!\n")

    # 3. Simulate Normal Operations (Creating Files)
    print("--- 📝 Simulating Standard File Operations ---")
    for i in range(1, 6):
        # We manually simulate allocation mapping for the demo
        blocks_needed = [10 + i, 20 + i, 30 + i] # Intentionally fragmented
        
        # Allocate blocks in Free Space Manager
        for b in blocks_needed:
            fsm.bitmap[b] = 1 
            
        # Add entry to FAT
        fat.file_to_blocks[i] = blocks_needed
        for b in blocks_needed:
            fat.block_to_file[b] = i

        # Write safely through the new Cache Manager
        cache.put(blocks_needed[0], f"DATA_FOR_FILE_{i}".encode('utf-8').ljust(512, b'\x00'))
        
        # Log to Journal
        txn_id = journal.begin_transaction('WRITE', {'inode': i, 'blocks': blocks_needed})
        journal.commit_transaction(txn_id)
        
    print(f"✅ Created 5 fragmented files.")
    print(f"📊 Initial Fragmentation: {defrag.analyze_fragmentation()['fragmentation_percentage']}%")
    print("\n")

    # 4. Triggering Defragmentation
    print("--- 🛠️ Running Background Defragmenter ---")
    defrag_report = defrag.defragment_all(strategy='most_fragmented_first')
    print(f"✅ Defragmentation Complete in {defrag_report['time_taken']:.4f}s")
    print(f"📊 Block Moves: {defrag_report['total_blocks_moved']}")
    print(f"📊 New Fragmentation: {defrag_report['final_fragmentation_percentage']}%\n")

    # 5. Injecting a Disaster Event
    print("--- 💥 INJECTING SEVERE HARDWARE CRASH ---")
    crash_event = simulator.inject_power_failure(disk, affected_blocks=[11, 12, 13])
    print(f"🚨 Crash Type Simulated: {crash_event['crash_type']}")
    print(f"🚨 Sectors Corrupted: {crash_event['affected_blocks']}\n")

    # 6. Recovery Pipeline
    print("--- 🚑 Commencing Automated Recovery ---")
    analysis = recovery_mgr.analyze_crash()
    print(f"🔍 Scan Result -> Corruption Detected: {analysis['has_corruption']}")
    
    if analysis['has_corruption'] or not analysis.get('success', True):
        print(f"🩹 Applying Action: Replaying Journal & Fixing Metadata...")
        recovery_result = recovery_mgr.recover_from_journal()
        if recovery_result['success']:
            print(f"✅ File System Restored Successfully! (Rolled back {len(recovery_result['rolled_back_transactions'])} transactions)")
        else:
            print("❌ Critical Failure: Unrecoverable disk state.")

    # 7. Post-Incident Performance Analysis
    print("\n--- 📈 Generating Final Performance Report ---")
    report = analyzer.generate_performance_report(output_format="text")
    print(report)

    print("\n=====================================================")
    print("🎉 END-TO-END DEMONSTRATION COMPLETE")
    print("=====================================================")

if __name__ == "__main__":
    run_demo()
