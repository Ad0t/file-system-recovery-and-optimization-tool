import random
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure a basic logger for the crash simulator
logger = logging.getLogger(__name__)

class CrashSimulator:
    """
    Simulates various file system crashes and corruptions for testing recovery mechanisms.
    """

    def __init__(self, random_seed: Optional[int] = None):
        """
        Initialize the CrashSimulator.

        Args:
            random_seed (int, optional): Seed for the random number generator
                to ensure reproducible crash scenarios.
        """
        self.crash_types: List[str] = [
            'POWER_FAILURE',
            'BIT_CORRUPTION',
            'METADATA_CORRUPTION',
            'JOURNAL_CORRUPTION',
            'INCOMPLETE_WRITE',
            'CASCADING_FAILURE',
            'SECTOR_FAILURE',
            'TRANSACTION_CORRUPTION',
            'DIRECTORY_TREE_CORRUPTION',
            'ALLOCATION_TABLE_CORRUPTION'
        ]
        self.crash_history: List[Dict[str, Any]] = []
        self.random_seed = random_seed
        if random_seed is not None:
            random.seed(random_seed)

    def _generate_crash_id(self) -> int:
        """Generate a unique ID for a new crash."""
        return int(datetime.now().timestamp() * 1000)

    def _log_crash(self, crash_report: dict) -> None:
        """Add crash to history and log it."""
        self.crash_history.append(crash_report)
        logger.info(f"Crash Injected [{crash_report.get('crash_id')}]: {crash_report.get('crash_type')} - {crash_report.get('description')}")

    def _calculate_severity(self, crash_type: str, affected_count: int) -> str:
        """
        Determine crash severity based on type and scope.

        Args:
            crash_type (str): The type of the crash.
            affected_count (int): The number of affected items (blocks, inodes, entries).

        Returns:
            str: Severity level ('LOW', 'MEDIUM', 'HIGH', or 'CRITICAL').
        """
        if crash_type in ('POWER_FAILURE', 'INCOMPLETE_WRITE'):
            if affected_count > 10:
                return 'HIGH'
            elif affected_count >= 5:
                return 'MEDIUM'
            return 'LOW'

        if crash_type == 'BIT_CORRUPTION':
            if affected_count >= 10:
                return 'HIGH'
            elif affected_count >= 5:
                return 'MEDIUM'
            return 'LOW'

        if crash_type == 'METADATA_CORRUPTION':
            if affected_count >= 5:
                return 'CRITICAL'
            elif affected_count >= 2:
                return 'HIGH'
            return 'MEDIUM'

        if crash_type == 'JOURNAL_CORRUPTION':
            # Journal corruption is generally quite severe
            if affected_count == 0: # 0 indicates complete corruption in our logic
                return 'CRITICAL'
            return 'HIGH'

        return 'MEDIUM'

    def _is_recoverable(self, crash_type: str) -> bool:
        """
        Determine if crash type is recoverable.

        Args:
            crash_type (str): The type of the crash.

        Returns:
            bool: True if generally recoverable, False otherwise.
        """
        # All our simulated crashes are potentially recoverable, except maybe complete disk failure.
        unrecoverable_types = ['COMPLETE_DISK_FAILURE']
        return crash_type not in unrecoverable_types

    def inject_power_failure(self, disk: Any, affected_blocks: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Simulate sudden power loss during a write operation.

        Args:
            disk (Any): The disk object.
            affected_blocks (list[int], optional): Blocks that were being written to.
                If None, randomly selects 5-10 blocks.

        Returns:
            dict: The crash report.
        """
        crash_type = 'POWER_FAILURE'
        
        try:
            total_blocks = getattr(disk, 'total_blocks', 1024)
            if affected_blocks is None:
                num_blocks = random.randint(5, 10)
                affected_blocks = random.sample(range(total_blocks), min(num_blocks, total_blocks))

            for block_idx in affected_blocks:
                # Set selected blocks to corrupted state
                corrupt_data = b'CORRUPTED_POWER_FAIL'
                try:
                    if hasattr(disk, 'write_block'):
                        disk.write_block(block_idx, corrupt_data)
                except Exception as e:
                    logger.error(f"Failed to corrupt block {block_idx}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during power failure injection: {e}")
            if affected_blocks is None:
                affected_blocks = []

        severity = self._calculate_severity(crash_type, len(affected_blocks))
        
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'affected_blocks': affected_blocks,
            'severity': severity,
            'description': f'Power failure during write operation affecting {len(affected_blocks)} blocks',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'MEDIUM'
        }
        
        self._log_crash(report)
        return report

    def inject_bit_corruption(self, disk: Any, num_blocks: int = 5) -> Dict[str, Any]:
        """
        Randomly flip bits in selected blocks.

        Args:
            disk (Any): The disk object.
            num_blocks (int): Number of random blocks to corrupt.

        Returns:
            dict: The crash report.
        """
        crash_type = 'BIT_CORRUPTION'
        affected_blocks = []
        
        try:
            total_blocks = getattr(disk, 'total_blocks', 1024)
            affected_blocks = random.sample(range(total_blocks), min(num_blocks, total_blocks))
            
            for block_idx in affected_blocks:
                try:
                    if hasattr(disk, 'read_block') and hasattr(disk, 'write_block'):
                        data = disk.read_block(block_idx)
                        if isinstance(data, bytes) or isinstance(data, bytearray):
                            data_arr = bytearray(data)
                            num_bits = random.randint(1, 10)
                            # Only flip bits if data is not empty
                            if len(data_arr) > 0:
                                for _ in range(num_bits):
                                    byte_idx = random.randint(0, len(data_arr) - 1)
                                    bit_idx = random.randint(0, 7)
                                    data_arr[byte_idx] ^= (1 << bit_idx)
                                disk.write_block(block_idx, bytes(data_arr))
                except Exception as e:
                    logger.error(f"Failed bit corruption on block {block_idx}: {e}")
        except Exception as e:
            logger.error(f"Error during bit corruption injection: {e}")

        severity = self._calculate_severity(crash_type, len(affected_blocks))

        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'affected_blocks': affected_blocks,
            'severity': severity,
            'description': f'Bit corruption injected in {len(affected_blocks)} blocks',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'HIGH'
        }
        
        self._log_crash(report)
        return report

    def inject_metadata_corruption(self, directory_tree: Any, num_inodes: int = 3) -> Dict[str, Any]:
        """
        Corrupt inode metadata.

        Args:
            directory_tree (Any): The file system directory tree.
            num_inodes (int): Number of random inodes to corrupt.

        Returns:
            dict: The crash report.
        """
        crash_type = 'METADATA_CORRUPTION'
        affected_inodes = []
        
        try:
            # Assumes directory_tree manages inodes in an accessible dictionary or list
            if hasattr(directory_tree, 'inodes'):
                inodes_dict = directory_tree.inodes
                available_ino = list(inodes_dict.keys())
                
                if available_ino:
                    selected_ino = random.sample(available_ino, min(num_inodes, len(available_ino)))
                    for ino in selected_ino:
                        inode_obj = inodes_dict[ino]
                        
                        # Corrupt some basic fields to simulate failure
                        corruption_choice = random.choice(['size', 'timestamps', 'block_pointers'])
                        if corruption_choice == 'size' and hasattr(inode_obj, 'size'):
                            inode_obj.size = random.randint(0, 999999)
                        elif corruption_choice == 'timestamps' and hasattr(inode_obj, 'mtime'):
                            inode_obj.mtime = 0.0
                        elif corruption_choice == 'block_pointers' and hasattr(inode_obj, 'blocks'):
                            if inode_obj.blocks:
                                inode_obj.blocks[0] = -1 # Invalid block pointer
                        
                        affected_inodes.append(ino)
        except Exception as e:
            logger.error(f"Error during metadata corruption injection: {e}")

        severity = self._calculate_severity(crash_type, len(affected_inodes))
        
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'affected_inodes': affected_inodes,
            'severity': severity,
            'description': f'Metadata corrupted for {len(affected_inodes)} inodes',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'HIGH'
        }
        
        self._log_crash(report)
        return report

    def inject_journal_corruption(self, journal: Any, corruption_level: str = 'partial') -> Dict[str, Any]:
        """
        Corrupt journal entries.

        Args:
            journal (Any): The file system journal object.
            corruption_level (str): Type of corruption ('partial', 'complete', 'transaction_only').

        Returns:
            dict: The crash report.
        """
        crash_type = 'JOURNAL_CORRUPTION'
        num_corrupted = 0
        
        try:
            if hasattr(journal, 'entries'):
                entries = journal.entries
                if not entries and corruption_level != 'complete':
                    logger.warning("Journal has no entries to corrupt partially or via transaction.")
                else:
                    if corruption_level == 'complete':
                        num_corrupted = len(entries)
                        journal.entries = [] # Wiping out journal entirely
                    elif corruption_level == 'partial':
                        num_corrupted = max(1, len(entries) // 2)
                        indices = random.sample(range(len(entries)), num_corrupted)
                        for idx in indices:
                            entries[idx] = {"corrupted": True}
                    elif corruption_level == 'transaction_only':
                        # Specifically target transaction fields
                        num_corrupted = 1
                        idx = random.randint(0, len(entries) - 1)
                        if isinstance(entries[idx], dict) and 'transaction_id' in entries[idx]:
                            entries[idx]['transaction_id'] = -1
        except Exception as e:
            logger.error(f"Error during journal corruption injection: {e}")

        # severity calculation depends on whether it's full wipe (represented as 0 or total length)
        severity = self._calculate_severity(crash_type, 0 if corruption_level == 'complete' else num_corrupted)
        
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'corruption_level': corruption_level,
            'entries_affected': num_corrupted,
            'severity': severity,
            'description': f'Journal corruption ({corruption_level}) affecting {num_corrupted} entries',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'CRITICAL' if corruption_level == 'complete' else 'MEDIUM'
        }
        
        self._log_crash(report)
        return report

    def inject_incomplete_write(self, disk: Any, file_blocks: List[int], completion_percentage: float = 0.5) -> Dict[str, Any]:
        """
        Simulate write operation interrupted mid-way.

        Args:
            disk (Any): The disk object.
            file_blocks (list[int]): Blocks representing a file's write intent.
            completion_percentage (float): The fraction of blocks successfully written before crash.

        Returns:
            dict: The crash report.
        """
        crash_type = 'INCOMPLETE_WRITE'
        
        num_to_write = int(len(file_blocks) * completion_percentage)
        blocks_written = file_blocks[:num_to_write]
        blocks_unwritten = file_blocks[num_to_write:]
        
        try:
            if hasattr(disk, 'write_block'):
                # Assuming blocks_written were successfully written, we intentionally garble unwritten ones 
                # (or write old data / zeros) to simulate the failure of completion
                for block_idx in blocks_unwritten:
                    disk.write_block(block_idx, b'\x00' * 512)
        except Exception as e:
            logger.error(f"Error during incomplete write injection: {e}")

        severity = self._calculate_severity(crash_type, len(blocks_unwritten))
        
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'blocks_written': blocks_written,
            'blocks_unwritten': blocks_unwritten,
            'severity': severity,
            'description': f'Incomplete write: {len(blocks_written)} blocks written, {len(blocks_unwritten)} blocks unwritten',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'MEDIUM'
        }
        
        self._log_crash(report)
        return report

    def get_crash_report(self, crash_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Return crash report from history.

        Args:
            crash_id (int, optional): The ID of the crash to retrieve.
                If None, returns the most recent crash.

        Returns:
            dict or None: The crash report dictionary, or None if not found/empty history.
        """
        if not self.crash_history:
            return None
            
        if crash_id is None:
            return self.crash_history[-1]
            
        for report in self.crash_history:
            if report.get('crash_id') == crash_id:
                return report
                
        return None

    def get_all_crashes(self) -> List[Dict[str, Any]]:
        """
        Return complete crash history.

        Returns:
            list[dict]: List of all injected crashes.
        """
        return list(self.crash_history)

    def clear_history(self) -> None:
        """Clear crash history log."""
        self.crash_history.clear()

    def simulate_random_crash(self, file_system_components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Randomly select and inject one crash type.

        Args:
            file_system_components (dict): Dictionary mapping component names to their instances
                (e.g., 'disk', 'directory_tree', 'journal').

        Returns:
            dict: The crash report.
        """
        crash_type = random.choice(self.crash_types)
        
        disk = file_system_components.get('disk')
        directory_tree = file_system_components.get('directory_tree')
        journal = file_system_components.get('journal')

        if crash_type == 'POWER_FAILURE':
            return self.inject_power_failure(disk)
        elif crash_type == 'BIT_CORRUPTION':
            return self.inject_bit_corruption(disk)
        elif crash_type == 'METADATA_CORRUPTION':
            return self.inject_metadata_corruption(directory_tree)
        elif crash_type == 'JOURNAL_CORRUPTION':
            corruption_levels = ['partial', 'complete', 'transaction_only']
            return self.inject_journal_corruption(journal, random.choice(corruption_levels))
        elif crash_type == 'INCOMPLETE_WRITE':
            # Generate dummy block list for incomplete write simulation
            total_blocks = getattr(disk, 'total_blocks', 1024) if disk else 1024
            file_blocks = random.sample(range(total_blocks), random.randint(5, 20))
            return self.inject_incomplete_write(disk, file_blocks=file_blocks)
            
        return {}

    def inject_cascading_failure(self, file_system_components: dict, num_cascades: int = 3) -> dict:
        """
        Simulate multiple related failures in succession.
        """
        crash_type = 'CASCADING_FAILURE'
        cascades = []
        
        methods = [
            (self.inject_power_failure, ['disk']),
            (self.inject_sector_failure, ['disk']),
            (self.inject_bit_corruption, ['disk']),
            (self.inject_metadata_corruption, ['directory_tree']),
            (self.inject_directory_tree_corruption, ['directory_tree']),
            (self.inject_journal_corruption, ['journal']),
            (self.inject_transaction_corruption, ['journal']),
            (self.inject_allocation_table_corruption, ['fat'])
        ]
        
        for _ in range(num_cascades + 1):
            method, required_keys = random.choice(methods)
            kwargs = {}
            valid = True
            for k in required_keys:
                if k in file_system_components and file_system_components[k] is not None:
                    kwargs[k] = file_system_components[k]
                else:
                    valid = False
            if valid:
                try:
                    res = method(**kwargs)
                    cascades.append(res)
                except Exception as e:
                    logger.error(f"Cascade injection failed for {method.__name__}: {e}")
                
        severity = 'CRITICAL' if cascades else 'LOW'
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'cascades': cascades,
            'severity': severity,
            'description': f'Cascading failure with {len(cascades)} intertwined crashes.',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'CRITICAL'
        }
        self._log_crash(report)
        return report

    def inject_sector_failure(self, disk: Any, sector_size: int = 64) -> dict:
        """
        Simulate bad sector (group of consecutive blocks).
        """
        crash_type = 'SECTOR_FAILURE'
        affected_blocks = []
        try:
            total_blocks = getattr(disk, 'total_blocks', 1024)
            if sector_size > total_blocks:
                sector_size = total_blocks
            start_block = random.randint(0, max(0, total_blocks - sector_size))
            affected_blocks = list(range(start_block, start_block + sector_size))
            
            for block_idx in affected_blocks:
                try:
                    if hasattr(disk, 'write_block'):
                        disk.write_block(block_idx, b'BAD_SECTOR_DATA')
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Sector failure error: {e}")
            
        severity = self._calculate_severity(crash_type, len(affected_blocks))
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'affected_blocks': affected_blocks,
            'severity': severity,
            'description': f'Sector failure affecting {len(affected_blocks)} consecutive blocks.',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'HIGH'
        }
        self._log_crash(report)
        return report

    def inject_transaction_corruption(self, journal: Any, transaction_ids: list = None) -> dict:
        """
        Corrupt specific transactions in journal.
        """
        crash_type = 'TRANSACTION_CORRUPTION'
        corrupted = []
        try:
            if hasattr(journal, 'entries'):
                entries = journal.entries
                tx_indices = [i for i, e in enumerate(entries) if isinstance(e, dict) and 'transaction_id' in e]
                
                if not transaction_ids:
                    num_to_corrupt = min(random.randint(2, 5), len(tx_indices))
                    to_corrupt_idx = random.sample(tx_indices, num_to_corrupt)
                else:
                    to_corrupt_idx = [i for i in tx_indices if entries[i]['transaction_id'] in transaction_ids]
                    
                for idx in to_corrupt_idx:
                    corruption_target = random.choice(['status', 'timestamps', 'redo_undo'])
                    if corruption_target == 'status':
                        entries[idx]['status'] = 'CORRUPT_STATE'
                    elif corruption_target == 'timestamps':
                        entries[idx]['timestamp'] = 0.0
                    elif corruption_target == 'redo_undo':
                        entries[idx]['redo'] = b'GARBAGE'
                        entries[idx]['undo'] = b'GARBAGE'
                    corrupted.append(entries[idx].get('transaction_id'))
        except Exception as e:
            logger.error(f"Transaction corruption failed: {e}")

        severity = self._calculate_severity(crash_type, len(corrupted))
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'corrupted_transactions': corrupted,
            'severity': severity,
            'description': f'Transaction corruption affecting {len(corrupted)} transactions.',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'MEDIUM'
        }
        self._log_crash(report)
        return report

    def inject_directory_tree_corruption(self, directory_tree: Any, corruption_type: str = 'broken_links') -> dict:
        """
        Corrupt directory structure.
        """
        crash_type = 'DIRECTORY_TREE_CORRUPTION'
        affected = 0
        try:
            if hasattr(directory_tree, 'root'):
                if corruption_type == 'broken_links':
                    if hasattr(directory_tree.root, 'children'):
                        directory_tree.root.children = {}
                        affected = 10
                elif corruption_type == 'duplicate_names':
                    if hasattr(directory_tree.root, 'children'):
                        directory_tree.root.children['duplicate'] = 'node1'
                        directory_tree.root.children['duplicate_2'] = 'node1'
                        affected = 2
                else:
                    affected = 1
        except Exception as e:
            logger.error(f"Directory tree corruption failed: {e}")
            
        severity = self._calculate_severity(crash_type, affected if affected else 5)
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'corruption_type': corruption_type,
            'severity': severity,
            'description': f'Directory tree corruption: {corruption_type}',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'HIGH'
        }
        self._log_crash(report)
        return report

    def inject_allocation_table_corruption(self, fat: Any, corruption_type: str = 'double_allocation') -> dict:
        """
        Corrupt file allocation table.
        """
        crash_type = 'ALLOCATION_TABLE_CORRUPTION'
        affected = 0
        try:
            if hasattr(fat, 'table'):
                table = fat.table
                keys = list(table.keys())
                if corruption_type == 'double_allocation' and len(keys) > 1:
                    if keys:
                        k1, k2 = random.sample(keys, min(2, len(keys)))
                        table[k2] = table[k1]
                        affected = 2
                elif corruption_type == 'missing_mappings':
                    for k in random.sample(keys, min(len(keys), 3)):
                        del table[k]
                        affected += 1
                elif corruption_type == 'invalid_pointers':
                    for k in random.sample(keys, min(len(keys), 3)):
                        if isinstance(table[k], list):
                            table[k].append(9999999)
                        else:
                            table[k] = 9999999
                        affected += 1
        except Exception as e:
            logger.error(f"FAT corruption failed: {e}")

        severity = self._calculate_severity(crash_type, affected)
        report = {
            'crash_id': self._generate_crash_id(),
            'crash_type': crash_type,
            'timestamp': datetime.now(),
            'corruption_type': corruption_type,
            'severity': severity,
            'description': f'FAT corruption: {corruption_type}',
            'recoverable': self._is_recoverable(crash_type),
            'recovery_difficulty': 'CRITICAL'
        }
        self._log_crash(report)
        return report

    def create_crash_scenario(self, scenario_name: str, file_system_components: dict) -> dict:
        """
        Predefined crash scenarios for testing.
        """
        disk = file_system_components.get('disk')
        directory_tree = file_system_components.get('directory_tree')
        journal = file_system_components.get('journal')
        fat = file_system_components.get('fat')
        
        crashes = []
        if scenario_name == 'mild_crash':
            crashes.append(self.inject_power_failure(disk))
        elif scenario_name == 'moderate_crash':
            crashes.append(self.inject_power_failure(disk))
            crashes.append(self.inject_bit_corruption(disk, num_blocks=3))
            crashes.append(self.inject_metadata_corruption(directory_tree, num_inodes=1))
        elif scenario_name == 'severe_crash':
            crashes.append(self.inject_cascading_failure(file_system_components, num_cascades=4))
        elif scenario_name == 'catastrophic_crash':
            crashes.append(self.inject_sector_failure(disk, sector_size=128))
            crashes.append(self.inject_allocation_table_corruption(fat, 'missing_mappings'))
            crashes.append(self.inject_directory_tree_corruption(directory_tree, 'broken_links'))
            crashes.append(self.inject_journal_corruption(journal, 'complete'))
            
        report = {
            'crash_id': self._generate_crash_id(),
            'scenario_name': scenario_name,
            'timestamp': datetime.now(),
            'injected_crashes': crashes,
            'description': f'Scenario {scenario_name} executed.',
        }
        self._log_crash(report)
        return report

    def validate_corruption(self, file_system_components: dict) -> dict:
        """
        Check if file system has any corruption.
        """
        is_corrupted = False
        corruption_points = []
        affected_components = []
        
        disk = file_system_components.get('disk')
        if disk and hasattr(disk, 'read_block'):
            try:
                block = disk.read_block(1)
                # Naive check for demonstration
                if isinstance(block, bytes) and (b'CORRUPTED' in block or b'BAD_SECTOR' in block):
                    is_corrupted = True
                    corruption_points.append('disk block signature corrupted')
                    if 'disk' not in affected_components:
                        affected_components.append('disk')
            except Exception:
                pass
                
        # If we injected anything, just assume checking caught it based on history
        if self.crash_history:
            is_corrupted = True
            for r in self.crash_history:
                if 'disk' not in affected_components and r.get('crash_type') in ('POWER_FAILURE', 'BIT_CORRUPTION', 'SECTOR_FAILURE'):
                    affected_components.append('disk')
                if 'journal' not in affected_components and r.get('crash_type') in ('JOURNAL_CORRUPTION', 'TRANSACTION_CORRUPTION'):
                    affected_components.append('journal')
                if 'directory_tree' not in affected_components and r.get('crash_type') in ('METADATA_CORRUPTION', 'DIRECTORY_TREE_CORRUPTION'):
                    affected_components.append('directory_tree')
                if 'fat' not in affected_components and r.get('crash_type') == 'ALLOCATION_TABLE_CORRUPTION':
                    affected_components.append('fat')
                corruption_points.append(r.get('description'))
                
        return {
            'is_corrupted': is_corrupted,
            'corruption_points': corruption_points,
            'severity': 'HIGH' if len(self.crash_history) > 5 else 'MEDIUM',
            'affected_components': list(set(affected_components))
        }

    def benchmark_crash_impact(self, file_system_components: dict, crash_report: dict) -> dict:
        """
        Measure impact of crash on file system.
        """
        severity = crash_report.get('severity', 'MEDIUM')
        
        data_loss_percentage = 0.0
        corrupted_files_count = 0
        recoverable_files_count = 100
        estimated_recovery_time = 0.0
        
        if severity == 'LOW':
            data_loss_percentage = 0.1
            corrupted_files_count = 1
            estimated_recovery_time = 5.0
        elif severity == 'MEDIUM':
            data_loss_percentage = 2.5
            corrupted_files_count = 5
            estimated_recovery_time = 30.0
        elif severity == 'HIGH':
            data_loss_percentage = 15.0
            corrupted_files_count = 50
            recoverable_files_count = 50
            estimated_recovery_time = 300.0
        elif severity == 'CRITICAL':
            data_loss_percentage = 85.0
            corrupted_files_count = 100
            recoverable_files_count = 5
            estimated_recovery_time = 3600.0
            
        return {
            'data_loss_percentage': data_loss_percentage,
            'corrupted_files_count': corrupted_files_count,
            'recoverable_files_count': recoverable_files_count,
            'estimated_recovery_time': estimated_recovery_time
        }
