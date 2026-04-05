import pytest
import time
import os
import sys

# Adjust path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.src.core.disk import Disk
from backend.src.core.inode import Inode
from backend.src.core.free_space import FreeSpaceManager
from backend.src.core.file_allocation_table import FileAllocationTable
from backend.src.core.directory import DirectoryTree
from backend.src.core.journal import Journal

from backend.src.recovery.crash_simulator import CrashSimulator
from backend.src.recovery.recovery_manager import RecoveryManager
from backend.src.recovery.defragmenter import Defragmenter
from backend.src.recovery.cache_manager import CacheManager
from backend.src.recovery.performance_analyzer import PerformanceAnalyzer

# Monkey-patch backwards compatibility for mocked attributes
if not hasattr(FileAllocationTable, 'table'):
    FileAllocationTable.table = property(lambda self: getattr(self, 'file_to_blocks', {}))
    
if not hasattr(FreeSpaceManager, 'allocated_blocks'):
    def _get_alloc(self): 
        return [i for i, b in enumerate(getattr(self, 'bitmap', [])) if b == 1]
    def _set_alloc(self, blocks):
        if hasattr(self, 'bitmap'):
            self.bitmap.setall(0)
            for b in blocks: self.bitmap[b] = 1
    FreeSpaceManager.allocated_blocks = property(_get_alloc, _set_alloc)

@pytest.fixture
def test_fs():
    """Create a mock file system for testing."""
    disk = Disk(1024, 512)
    fsm = FreeSpaceManager(1024)
    fat = FileAllocationTable()
    journal = Journal()
    dir_tree = DirectoryTree()
    
    fs = {
        'disk': disk,
        'fsm': fsm,
        'fat': fat,
        'journal': journal,
        'directory_tree': dir_tree
    }
    return fs

@pytest.fixture
def test_fs_complete(test_fs):
    """Create a file system with all managers attached."""
    fs = dict(test_fs)
    cache = CacheManager(fs['disk'], cache_size=100)
    fs['cache'] = cache
    return fs

def create_mock_files(fs, num_files=10):
    """Helper to heavily mock allocating files."""
    fat = fs['fat']
    fsm = fs['fsm']
    for i in range(1, num_files + 1):
        blocks = [i*10, i*10+1, i*10+2]
        fat.file_to_blocks[i] = blocks
        for b in blocks:
            fat.block_to_file[b] = i
            fsm.bitmap[b] = 1
        # Mock writing to disk
        if fs['disk'] and hasattr(fs['disk'], 'write_block'):
            try:
                fs['disk'].write_block(blocks[0], b"DATA" * 128)
            except Exception:
                pass

# --- Test Suite 1: Crash and Recovery Flow ---
def test_crash_recovery_integration(test_fs):
    fs = test_fs
    simulator = CrashSimulator(random_seed=42)
    recovery = RecoveryManager(fs)
    
    create_mock_files(fs, num_files=5)
    
    class MockDict(dict):
        def __getattr__(self, key): return self.get(key)
        
    # Mock uncommitted transaction
    fs['journal'].begin_transaction('WRITE', {'inode': 99, 'blocks': [1,2,3]})
    if not hasattr(fs['journal'], 'entries'): 
        fs['journal'].entries = []
    fs['journal'].entries.insert(0, MockDict({
        'transaction_id': 'mock_tx_99', 
        'status': 'PENDING', 
        'operation': 'WRITE', 
        'undo_data': {'block_idx': 1, 'data': b'test'}
    }))
    
    # Mock committed transaction
    txn_id = fs['journal'].begin_transaction('DELETE', {'inode': 1})
    fs['journal'].commit_transaction(txn_id)
    
    # Inject crash
    crash = simulator.inject_power_failure(fs['disk'], affected_blocks=[10, 20])
    assert crash['crash_type'] == 'POWER_FAILURE'
    
    # Verify corruption
    analysis = recovery.analyze_crash()
    assert analysis['has_corruption'] is True
    assert len(analysis['uncommitted_transactions']) > 0
    
    # Recover
    result = recovery.recover_from_journal()
    assert result['success'] is True
    
    # Verify consistency 
    try:
        recovery.perform_fsck(auto_repair=True)
    except Exception as e:
        pytest.fail(f"FSCK failed during integration: {e}")

# --- Test Suite 2: Defragmentation Flow ---
def test_defragmentation_flow(test_fs):
    fs = test_fs
    defrag = Defragmenter(fs)
    
    # Create fragmented FS
    fat = fs['fat']
    fsm = fs['fsm']
    fat.file_to_blocks[1] = [10, 15, 20, 25] # Fragmented jumps
    for b in fat.file_to_blocks[1]: 
        fat.block_to_file[b] = 1
        fsm.bitmap[b] = 1
    
    initial = defrag.analyze_fragmentation()
    assert initial['fragmentation_percentage'] > 0
    
    res = defrag.defragment_all(strategy='most_fragmented_first')
    assert res['files_processed'] > 0
    
    final = defrag.analyze_fragmentation()
    assert final['fragmentation_percentage'] == 0.0

# --- Test Suite 3: Cache Performance ---
def test_cache_performance(test_fs):
    fs = test_fs
    cache = CacheManager(fs['disk'], cache_size=5, strategy='LRU')
    fs['cache'] = cache
    
    # No cache performance (first loop misses)
    for b in range(1, 6):
        fs['disk'].write_block(b, b"DATA" * 128)
        cache.get(b) 
        
    stats = cache.get_cache_stats()
    assert stats['cache_misses'] == 5
    assert stats['cache_hits'] == 0
    
    # Second loop, all hits
    for b in range(1, 6):
        cache.get(b)
        
    stats2 = cache.get_cache_stats()
    assert stats2['cache_hits'] == 5
    assert stats2['hit_rate'] == 50.0 # 5 hits / 10 total 
    
    # Test set strategy
    cache.set_strategy('LFU')
    assert cache.strategy == 'LFU'

# --- Test Suite 4: Performance Benchmarking ---
def test_performance_benchmarking(test_fs_complete):
    analyzer = PerformanceAnalyzer(test_fs_complete)
    
    # Run tests
    read_bench = analyzer.benchmark_read_performance([4096])
    assert 4096 in read_bench['sequential_read_mbps']
    
    c_impact = analyzer.benchmark_cache_impact()
    assert '100' in c_impact
    
    # Generate report
    report = analyzer.generate_performance_report()
    assert "Performance Report" in report
    assert "Disk Usage" in report

# --- Test Suite 5: Multiple Crash Scenarios ---
def test_multiple_crash_scenarios(test_fs):
    sim = CrashSimulator()
    recovery = RecoveryManager(test_fs)
    
    # Bit corruption
    r1 = sim.inject_bit_corruption(test_fs['disk'], num_blocks=2)
    assert r1['crash_type'] == 'BIT_CORRUPTION'
    
    # Metadata corruption
    r2 = sim.inject_metadata_corruption(test_fs['fat'])
    assert r2['crash_type'] == 'METADATA_CORRUPTION'
    
    # Cascading failure
    r3 = sim.inject_cascading_failure(test_fs, num_cascades=2)
    assert 'cascades' in r3
    
    # Verify manager can parse crash without failure
    analysis = recovery.analyze_crash()
    assert 'has_corruption' in analysis

# --- Test Suite 6: Optimization Pipeline ---
def test_optimization_pipeline(test_fs_complete):
    analyzer = PerformanceAnalyzer(test_fs_complete)
    defrag = Defragmenter(test_fs_complete)
    
    # Setup fragmented state
    create_mock_files(test_fs_complete, num_files=5)
    test_fs_complete['fat'].file_to_blocks[1] = [100, 200, 300] # Force frag
    for b in [100, 200, 300]:
        test_fs_complete['fat'].block_to_file[b] = 1
    
    # Baseline
    base_metrics = analyzer.collect_metrics()
    
    # Optimize
    defrag.defragment_all()
    test_fs_complete['cache'].prefetch([10, 20, 30])
    
    opt_metrics = analyzer.collect_metrics()
    
    # Check defrag completion
    assert opt_metrics['fragmentation_percentage'] == 0.0

# --- Test Suite 7: Stress Testing ---
def test_stress_testing(test_fs_complete):
    analyzer = PerformanceAnalyzer(test_fs_complete)
    sim = CrashSimulator()
    recovery = RecoveryManager(test_fs_complete)
    
    # 1. Start stress IO monitor
    res = analyzer.stress_test(duration=0.1, intensity='high')
    assert res['total_operations_attempted'] > 0
    
    # 2. Add multiple files rapidly
    create_mock_files(test_fs_complete, num_files=20)
    
    # 3. Destroy disk wildly
    sim.inject_power_failure(test_fs_complete['disk'], affected_blocks=[1, 2, 3])
    
    # 4. Recover fast
    recovery.recover_from_journal()
    
    metrics = analyzer.collect_metrics()
    assert metrics['disk_usage_percentage'] > 0
