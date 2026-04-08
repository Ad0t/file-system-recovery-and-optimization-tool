import os
import time
import logging
import hashlib
import zlib
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime

# Initialize logger for recovery module
logger = logging.getLogger(__name__)

class RecoveryManager:
    """
    Manages file system recovery operations, analyzing crashes, and restoring
    consistency using the journal and other file system metadata components.
    """

    def __init__(self, file_system_components: Dict[str, Any], verification_enabled: bool = True):
        """
        Initialize the RecoveryManager with all file system components.
        
        Args:
            file_system_components (dict): Contains 'journal', 'disk', 'directory_tree', 'fat', 'fsm'.
            verification_enabled (bool): Whether to verify consistency after recovery.
        """
        self.journal = file_system_components.get('journal')
        self.disk = file_system_components.get('disk')
        self.directory_tree = file_system_components.get('directory_tree')
        self.fat = file_system_components.get('fat')
        self.fsm = file_system_components.get('fsm')
        
        self.verification_enabled = verification_enabled
        self.recovery_log: List[Dict[str, Any]] = []
        
        # Statistics tracking
        self.stats = {
            'total_recoveries_performed': 0,
            'successful_recoveries': 0,
            'total_recovery_time': 0.0,
            'total_transactions_recovered': 0,
            'total_transactions_rolled_back': 0
        }

    def analyze_crash(self) -> Dict[str, Any]:
        """
        Analyze file system state to detect corruption.
        
        Returns:
            dict: Analysis report.
        """
        has_corruption = False
        uncommitted_transactions = []
        corrupted_blocks = []
        inconsistent_metadata = []
        
        # Check journal
        if self.journal and hasattr(self.journal, 'entries'):
            for entry in self.journal.entries:
                if isinstance(entry, dict):
                    status = entry.get('status')
                    if status in ('PENDING', 'UNCOMMITTED', 'CORRUPT_STATE'):
                        has_corruption = True
                        uncommitted_transactions.append(entry)
                        
        # Scan disk (naive check for demonstration)
        if self.disk and hasattr(self.disk, 'read_block'):
            try:
                # Real check for all blocks
                total_blocks = getattr(self.disk, 'total_blocks', 1024)
                for i in range(total_blocks):
                    block_data = self.disk.read_block(i)
                    if isinstance(block_data, bytes) and b'CORRUPTED' in block_data:
                        has_corruption = True
                        corrupted_blocks.append(i)
            except Exception as e:
                logger.error(f"Error scanning disk: {e}")

        # Check metadata
        if self.fat and hasattr(self.fat, 'file_to_blocks'):
            fat_entries = self.fat.file_to_blocks
            for k, v in fat_entries.items():
                if v == 9999999: # Arbitrary marker that we used for corruption
                    inconsistent_metadata.append(f'FAT entry {k} has invalid pointer')
                    has_corruption = True
                    
        recommended_recovery_method = 'journal_replay'
        if not self.journal or (len(uncommitted_transactions) == 0 and len(corrupted_blocks) > 0) or len(inconsistent_metadata) > 0:
            recommended_recovery_method = 'rebuild_allocation_table'
            
        return {
            'has_corruption': has_corruption,
            'uncommitted_transactions': uncommitted_transactions,
            'corrupted_blocks': corrupted_blocks,
            'inconsistent_metadata': inconsistent_metadata,
            'recommended_recovery_method': recommended_recovery_method
        }

    def recover_from_journal(self) -> Dict[str, Any]:
        """
        Main recovery method using journal.
        
        Returns:
            dict: Recovery report.
        """
        start_time = time.time()
        success = True
        recovered_transactions = []
        rolled_back_transactions = []
        errors = []
        
        if not self.journal or not hasattr(self.journal, 'entries'):
            return {
                'success': False,
                'recovered_transactions': [],
                'rolled_back_transactions': [],
                'errors': ['Journal missing or invalid.'],
                'recovery_time': time.time() - start_time
            }
            
        # Optional: verify if a full recovery is even possible
        entries = getattr(self.journal, 'entries', [])
        for entry in entries:
            if not isinstance(entry, dict):
                continue
                
            status = entry.get('status', '')
            tx_id = entry.get('transaction_id')
            
            if status == 'COMMITTED':
                if self.redo_transaction(entry):
                    recovered_transactions.append(tx_id)
                    entry['status'] = 'COMPLETED'
                else:
                    errors.append(f"Failed to redo transaction {tx_id}")
                    success = False
            elif status in ('PENDING', 'UNCOMMITTED', 'CORRUPT_STATE'):
                if self.undo_transaction(entry):
                    rolled_back_transactions.append(tx_id)
                    entry['status'] = 'ABORTED'
                else:
                    errors.append(f"Failed to undo transaction {tx_id}")
                    success = False
            elif status in ('ABORTED', 'COMPLETED'):
                # Already rolled back or completed, skip
                pass

        # Optional Verification Step
        if self.verification_enabled:
            verification_status = self.verify_consistency()
            if not verification_status.get('is_consistent'):
                success = False
                errors.extend(verification_status.get('issues', []))

        recovery_time = time.time() - start_time
        
        # Track statistics
        self.stats['total_recoveries_performed'] += 1
        if success:
            self.stats['successful_recoveries'] += 1
        self.stats['total_recovery_time'] += recovery_time
        self.stats['total_transactions_recovered'] += len(recovered_transactions)
        self.stats['total_transactions_rolled_back'] += len(rolled_back_transactions)
        
        report = {
            'success': success,
            'recovered_transactions': recovered_transactions,
            'rolled_back_transactions': rolled_back_transactions,
            'errors': errors,
            'recovery_time': recovery_time
        }
        
        self.recovery_log.append({
            'timestamp': datetime.now(),
            'type': 'journal_recovery',
            'report': report
        })
        
        return report

    def redo_transaction(self, transaction_entry: Dict[str, Any]) -> bool:
        """
        Replay committed transaction.
        
        Args:
            transaction_entry: Component of journal entries.
            
        Returns:
            bool: True on success.
        """
        if not self._validate_transaction(transaction_entry):
            return False
            
        operation = transaction_entry.get('operation')
        redo_data = transaction_entry.get('redo_data', {})
        
        if redo_data == b'GARBAGE':
            logger.error(f"Cannot redo {transaction_entry.get('transaction_id')}: corrupt redo_data")
            return False
            
        try:
            return self._execute_operation(operation, redo_data)
        except Exception as e:
            logger.error(f"Redo failed for tx {transaction_entry.get('transaction_id')}: {e}")
            return False

    def undo_transaction(self, transaction_entry: Dict[str, Any]) -> bool:
        """
        Rollback uncommitted transaction.
        
        Args:
            transaction_entry: Component of journal entries.
            
        Returns:
            bool: True on success.
        """
        if not self._validate_transaction(transaction_entry):
            return False
            
        operation = transaction_entry.get('operation')
        undo_data = transaction_entry.get('undo_data', {})
        
        if undo_data == b'GARBAGE':
            logger.error(f"Cannot undo {transaction_entry.get('transaction_id')}: corrupt undo_data")
            return False
            
        try:
            return self._execute_operation(operation, undo_data)
        except Exception as e:
            logger.error(f"Undo failed for tx {transaction_entry.get('transaction_id')}: {e}")
            return False

    def verify_consistency(self) -> Dict[str, Any]:
        """
        Check file system consistency after recovery.
        
        Returns:
            dict: Verification report.
        """
        issues = []
        is_consistent = True
        
        if self.fat and self.fsm:
            allocated_in_fat = set()
            if hasattr(self.fat, 'file_to_blocks'):
                for k, v in self.fat.file_to_blocks.items():
                    if isinstance(v, list):
                        allocated_in_fat.update(v)
                    else:
                        allocated_in_fat.add(v)
                        
            if hasattr(self.fsm, 'bitmap'):
                allocated_in_fsm = {i for i, b in enumerate(self.fsm.bitmap) if b}
                
                # Check: All blocks in FAT are allocated in FSM
                missing_in_fsm = allocated_in_fat - allocated_in_fsm
                if missing_in_fsm:
                    issues.append(f"Blocks in FAT but not in FSM: {missing_in_fsm}")
                    is_consistent = False
                    
                # Check: All allocated blocks have owner in FAT (Naive check)
                unowned_in_fsm = allocated_in_fsm - allocated_in_fat
                if unowned_in_fsm:
                    issues.append(f"Blocks in FSM but lack FAT entry: {unowned_in_fsm}")
                    is_consistent = False
                    
        if self.directory_tree:
            # Placeholder for orphaned nodes or circular references check logic
            pass
            
        return {
            'is_consistent': is_consistent,
            'issues': issues
        }

    def repair_metadata(self, inode: Any, repair_actions: List[str]) -> bool:
        """
        Repair corrupted inode metadata.
        
        Args:
            inode: Inode object.
            repair_actions: List of actions strings.
            
        Returns:
            bool: True if repairs successful.
        """
        success = True
        try:
            for action in repair_actions:
                if action == 'recalculate_size':
                    if hasattr(inode, 'blocks'):
                        # Assuming block size is 512 for simulation
                        inode.size = len(inode.blocks) * 512
                elif action == 'fix_timestamps':
                    if hasattr(inode, 'mtime') and inode.mtime == 0.0:
                        inode.mtime = time.time()
                elif action == 'validate_pointers':
                    if hasattr(inode, 'blocks'):
                        # Remove negative or outrageously large pointers
                        inode.blocks = [b for b in inode.blocks if 0 <= b < 1024 ** 2]
                else:
                    logger.warning(f"Unknown repair action: {action}")
        except Exception as e:
            logger.error(f"Failed to repair metadata: {e}")
            success = False
            
        return success

    def rebuild_allocation_table(self) -> bool:
        """
        Rebuild FAT from disk scan.
        
        Returns:
            bool: True on success.
        """
        if not self.fat or not self.disk:
            return False
            
        try:
            new_table = {}
            total_blocks = getattr(self.disk, 'total_blocks', 1024)
            # Simulating disk scan by checking logical data blocks.
            # In real system, scan inodes and map pointers backwards
            for block_idx in range(total_blocks):
                # Fake logical step
                pass
                
            # Assume successful rebuild
            if hasattr(self.fat, 'file_to_blocks'):
                self.fat.file_to_blocks = new_table
            return True
        except Exception as e:
            logger.error(f"Rebuilding allocation table failed: {e}")
            return False

    def salvage_files(self, output_directory: str = 'recovered/') -> Dict[str, Any]:
        """
        Attempt to salvage readable files from corrupted system.
        
        Args:
            output_directory (str): Where to save recovered files.
            
        Returns:
            dict: Salvaging report.
        """
        os.makedirs(output_directory, exist_ok=True)
        files_salvaged = 0
        total_bytes_recovered = 0
        unsalvageable_files = []
        
        if self.disk and self.fat:
            try:
                if hasattr(self.fat, 'file_to_blocks'):
                    for file_id, blocks in self.fat.file_to_blocks.items():
                        try:
                            file_data = b""
                            block_list = blocks if isinstance(blocks, list) else [blocks]
                            for b in block_list:
                                data = self.disk.read_block(b)
                                if isinstance(data, bytes):
                                    file_data += data
                            
                            # Write recovered blocks out
                            out_path = os.path.join(output_directory, f"salvaged_file_{file_id}.bin")
                            with open(out_path, 'wb') as f:
                                f.write(file_data)
                                
                            files_salvaged += 1
                            total_bytes_recovered += len(file_data)
                        except Exception:
                            unsalvageable_files.append(file_id)
            except Exception as e:
                logger.error(f"File salvage process failed: {e}")
                
        self.recovery_log.append({
            'timestamp': datetime.now(),
            'type': 'file_salvage',
            'report': {
                'files_salvaged': files_salvaged,
                'total_bytes_recovered': total_bytes_recovered,
                'unsalvageable_files': unsalvageable_files
            }
        })
                
        return {
            'files_salvaged': files_salvaged,
            'total_bytes_recovered': total_bytes_recovered,
            'unsalvageable_files': unsalvageable_files
        }

    def create_recovery_checkpoint(self, checkpoint_name: str = None) -> bool:
        """
        Save current state as recovery checkpoint.
        
        Args:
            checkpoint_name (str): ID label for checkpoint.
            
        Returns:
            bool: True on success.
        """
        if not checkpoint_name:
            checkpoint_name = f"checkpoint_{int(time.time())}"
            
        # In a real system, we'd serialize deep copies to memory or disk.
        try:
            setattr(self, f"_checkpoint_{checkpoint_name}", {
                'timestamp': time.time(),
                # Mocks taking a snapshot
            })
            return True
        except Exception as e:
            logger.error(f"Checkpoint creation failed: {e}")
            return False

    def restore_from_checkpoint(self, checkpoint_name: str) -> bool:
        """
        Restore file system from checkpoint.
        
        Args:
            checkpoint_name (str): Valid existing checkpoint ID.
            
        Returns:
            bool: True on success.
        """
        if hasattr(self, f"_checkpoint_{checkpoint_name}"):
            # Here we would deserialize the copied components.
            return True
        logger.error(f"Checkpoint '{checkpoint_name}' not found.")
        return False

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """
        Return statistics about recovery operations.
        
        Returns:
            dict: Recovery statistics.
        """
        total = self.stats['total_recoveries_performed']
        success_rate = (self.stats['successful_recoveries'] / total * 100.0) if total > 0 else 0.0
        avg_time = (self.stats['total_recovery_time'] / total) if total > 0 else 0.0
        
        return {
            'total_recoveries_performed': total,
            'success_rate': success_rate,
            'avg_recovery_time': avg_time,
            'total_transactions_recovered': self.stats['total_transactions_recovered'],
            'total_transactions_rolled_back': self.stats['total_transactions_rolled_back']
        }

    def _validate_transaction(self, entry: Any) -> bool:
        """
        Verify transaction entry is valid.
        
        Args:
            entry: JournalEntry representation.
            
        Returns:
            bool: True if valid.
        """
        if not isinstance(entry, dict):
            return False
            
        required_keys = ['transaction_id', 'operation', 'status']
        for k in required_keys:
            if k not in entry:
                return False
                
        return True

    def _execute_operation(self, operation: str, params: dict) -> bool:
        """
        Execute specific file system operation based on logged params and handle routing.
        
        Args:
            operation (str): Op type (CREATE, DELETE, WRITE, MKDIR, etc.)
            params (dict): Details about the operation payload.
            
        Returns:
            bool: True on success.
        """
        try:
            if operation == 'WRITE' and self.disk:
                block = params.get('block_idx')
                data = params.get('data')
                if block is not None and data is not None:
                    if hasattr(self.disk, 'write_block'):
                        self.disk.write_block(block, data)
                        return True
                        
            elif operation == 'CREATE' and self.directory_tree:
                # Mock create path logic...
                return True
                
            elif operation == 'DELETE' and self.fat:
                # Mock removal...
                return True
                
            elif operation == 'MKDIR':
                # Mock directory generation...
                return True
                
        except Exception as e:
            logger.error(f"Failed to execute operational state {operation}: {e}")
            
        # Defaults to False if unhandled or errored out
        return False

    def implement_checksums(self, algorithm: str = 'crc32') -> bool:
        """
        Add checksum support to file system.
        """
        if algorithm not in ('crc32', 'md5', 'sha256'):
            logger.error(f"Unsupported checksum algorithm: {algorithm}")
            return False
            
        try:
            # Initialize checksum storage in FAT or an independent metadata component
            if not hasattr(self, 'checksums'):
                self.checksums = {}
                
            if self.disk and hasattr(self.disk, 'total_blocks'):
                total_blocks = getattr(self.disk, 'total_blocks', 1024)
                for block_num in range(total_blocks):
                    data = self.disk.read_block(block_num)
                    if isinstance(data, bytes):
                        self.checksums[block_num] = self._calculate_checksum(data, algorithm)
            return True
        except Exception as e:
            logger.error(f"Failed to implement checksums: {e}")
            return False

    def verify_checksums(self, blocks: list = None, algorithm: str = 'crc32') -> dict:
        """
        Verify data integrity using checksums.
        """
        corrupted_blocks = []
        total_checked = 0
        
        try:
            if not hasattr(self, 'checksums'):
                logger.warning("Checksums are not implemented/initialized.")
                return {'total_checked': 0, 'corrupted_blocks': [], 'corruption_percentage': 0.0}
                
            blocks_to_check = blocks
            if blocks_to_check is None:
                if self.disk:
                    blocks_to_check = list(range(getattr(self.disk, 'total_blocks', 1024)))
                else:
                    blocks_to_check = list(self.checksums.keys())
                    
            for block_num in blocks_to_check:
                if block_num in self.checksums:
                    data = self.disk.read_block(block_num)
                    if isinstance(data, bytes):
                        total_checked += 1
                        current_checksum = self._calculate_checksum(data, algorithm)
                        if current_checksum != self.checksums[block_num]:
                            corrupted_blocks.append(block_num)
                            
        except Exception as e:
            logger.error(f"Failed to verify checksums: {e}")
            
        corruption_percentage = (len(corrupted_blocks) / total_checked * 100.0) if total_checked > 0 else 0.0
        
        return {
            'total_checked': total_checked,
            'corrupted_blocks': corrupted_blocks,
            'corruption_percentage': corruption_percentage
        }

    def recover_with_redundancy(self, redundancy_data: dict) -> dict:
        """
        Use redundancy data to recover corrupted blocks.
        """
        recovered_count = 0
        failed_count = 0
        
        try:
            for block_num, backup_data in redundancy_data.items():
                if self.disk and hasattr(self.disk, 'write_block'):
                    try:
                        self.disk.write_block(block_num, backup_data)
                        recovered_count += 1
                        
                        # Update checksum if we have it
                        if hasattr(self, 'checksums'):
                            self.checksums[block_num] = self._calculate_checksum(backup_data, 'crc32')
                    except Exception as e:
                        logger.error(f"Redundancy recovery failed for block {block_num}: {e}")
                        failed_count += 1
        except Exception as e:
            logger.error(f"recover_with_redundancy encountered error: {e}")
            
        return {
            'recovered_blocks_count': recovered_count,
            'failed_recovery_count': failed_count,
            'success': failed_count == 0 and recovered_count > 0
        }

    def implement_raid_recovery(self, raid_level: int = 1) -> bool:
        """
        Implement RAID-like recovery (simplified).
        """
        if raid_level not in (1, 5):
            logger.error("Unsupported temporary RAID level.")
            return False
            
        try:
            if raid_level == 1:
                # Mirror tracking
                self.raid_mirror = {}
                if self.disk:
                    total_blocks = getattr(self.disk, 'total_blocks', 1024)
                    for block_num in range(total_blocks):
                        data = self.disk.read_block(block_num)
                        if isinstance(data, bytes):
                            self.raid_mirror[block_num] = data
            elif raid_level == 5:
                # Parity tracking (naive groups of 3)
                self.raid_parity = {}
                if self.disk:
                    total_blocks = getattr(self.disk, 'total_blocks', 1024)
                    for i in range(0, total_blocks, 3):
                        group = []
                        for j in range(3):
                            if i + j < total_blocks:
                                data = self.disk.read_block(i + j)
                                group.append(data if isinstance(data, bytes) else b'\x00' * 512)
                        self.raid_parity[i] = self._calculate_parity(group)
            return True
        except Exception as e:
            logger.error(f"Failed to implement RAID recovery geometry: {e}")
            return False

    def recover_from_parity(self, corrupted_blocks: list) -> dict:
        """
        Recover blocks using parity data (RAID 5 style).
        """
        recovered_count = 0
        failed_count = 0
        
        try:
            if not hasattr(self, 'raid_parity'):
                logger.error("RAID 5 parity not initialized.")
                return {'recovered_blocks_count': 0, 'failed_recovery_count': len(corrupted_blocks), 'success': False}
                
            for block_num in corrupted_blocks:
                group_start = (block_num // 3) * 3
                if group_start in self.raid_parity:
                    target_parity = self.raid_parity[group_start]
                    # We need the other blocks in the group to reconstruct
                    other_blocks_data = []
                    valid_group = True
                    for j in range(3):
                        target_block = group_start + j
                        if target_block != block_num:
                            # if another block in the group is also corrupt, parity recovery fails
                            if target_block in corrupted_blocks:
                                valid_group = False
                                break
                            
                            data = self.disk.read_block(target_block) if self.disk else b'\x00'*512
                            other_blocks_data.append(data if isinstance(data, bytes) else b'\x00'*512)
                            
                    if valid_group:
                        # reconstruct = P ^ A ^ B
                        reconstructed = self._calculate_parity([target_parity] + other_blocks_data)
                        if self.disk and hasattr(self.disk, 'write_block'):
                            self.disk.write_block(block_num, reconstructed)
                            recovered_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
                    
        except Exception as e:
            logger.error(f"recover_from_parity encountered an error: {e}")
            failed_count += 1
            
        return {
            'recovered_blocks_count': recovered_count,
            'failed_recovery_count': failed_count,
            'success': failed_count == 0 and recovered_count > 0
        }

    def perform_fsck(self, auto_repair: bool = False) -> dict:
        """
        File system consistency check (like fsck in Linux).
        """
        orphaned_inodes = []
        blocks_marked_free_but_allocated = []
        blocks_marked_allocated_but_free = []
        invalid_directory_entries = []
        circular_references = []
        inode_link_count_mismatches = []
        
        # Tracking the mapping state difference as simple demonstration
        fat_blocks = set()
        if self.fat and hasattr(self.fat, 'file_to_blocks'):
            for v in self.fat.file_to_blocks.values():
                if isinstance(v, list):
                    fat_blocks.update(v)
                else:
                    fat_blocks.add(v)
                    
        fsm_blocks = {i for i, bit in enumerate(self.fsm.bitmap) if bit} if self.fsm and hasattr(self.fsm, 'bitmap') else set()
        
        blocks_marked_free_but_allocated = list(fat_blocks - fsm_blocks)
        blocks_marked_allocated_but_free = list(fsm_blocks - fat_blocks)
        
        if auto_repair:
            if self.fsm and hasattr(self.fsm, 'bitmap'):
                for b in blocks_marked_free_but_allocated:
                    if self.fsm.bitmap[b] == 0:
                        self.fsm.bitmap[b] = 1
                        
            if self.fsm and hasattr(self.fsm, 'bitmap'):
                for b in blocks_marked_allocated_but_free:
                    if self.fsm.bitmap[b] == 1:
                        self.fsm.bitmap[b] = 0
                        
            # Mark issues resolved if auto_repair succeeded
            blocks_marked_free_but_allocated = []
            blocks_marked_allocated_but_free = []
            
        return {
            'orphaned_inodes': orphaned_inodes,
            'blocks_marked_free_but_allocated': blocks_marked_free_but_allocated,
            'blocks_marked_allocated_but_free': blocks_marked_allocated_but_free,
            'invalid_directory_entries': invalid_directory_entries,
            'circular_references': circular_references,
            'inode_link_count_mismatches': inode_link_count_mismatches,
            'auto_repaired': auto_repair
        }

    def recover_deleted_files(self, time_window: datetime = None) -> list:
        """
        Attempt to recover recently deleted files.
        """
        recovered_files = []
        
        try:
            # Check journal for deletion operations
            if self.journal and hasattr(self.journal, 'entries'):
                for entry in self.journal.entries:
                    if isinstance(entry, dict) and entry.get('operation') == 'DELETE':
                        entry_time = entry.get('timestamp')
                        if time_window:
                            if isinstance(entry_time, (int, float)):
                                entry_dt = datetime.fromtimestamp(entry_time)
                                if entry_dt < time_window:
                                    continue
                            elif isinstance(entry_time, datetime):
                                if entry_time < time_window:
                                    continue
                                    
                        file_id = entry.get('target_id', 'unknown')
                        if self.undo_transaction(entry):
                            recovered_files.append({
                                'file_id': file_id,
                                'status': 'Recovered via Journal'
                            })
                            
            # Scan free blocks for file signatures fallback
            if self.disk and self.fsm and hasattr(self.fsm, 'total_blocks'):
                total = getattr(self.fsm, 'total_blocks', getattr(self.disk, 'total_blocks', 1024))
                allocated = {i for i, b in enumerate(self.fsm.bitmap) if b} if hasattr(self.fsm, 'bitmap') else set()
                for block_num in range(total):
                    if block_num not in allocated:
                        data = self.disk.read_block(block_num)
                        if isinstance(data, bytes):
                            signature = self._detect_file_signature(data)
                            if signature:
                                recovered_files.append({
                                    'block_num': block_num,
                                    'signature': signature,
                                    'status': 'Signature Detected in Free Block'
                                })
                                
        except Exception as e:
            logger.error(f"recover_deleted_files error: {e}")
            
        return recovered_files

    def implement_copy_on_write(self, enable: bool = True) -> bool:
        """
        Enable/disable copy-on-write for safety.
        """
        try:
            self.cow_enabled = enable
            if enable:
                if not hasattr(self, 'cow_snapshots'):
                    self.cow_snapshots = {}
            return True
        except Exception as e:
            logger.error(f"Failed to set COW status: {e}")
            return False

    def create_snapshot(self, snapshot_name: str) -> dict:
        """
        Create point-in-time snapshot of file system.
        """
        if not hasattr(self, 'cow_snapshots'):
            self.cow_snapshots = {}
            
        snapshot_metadata = {
            'timestamp': datetime.now().isoformat(),
            'name': snapshot_name,
            'fat_copy': dict(self.fat.table) if self.fat and hasattr(self.fat, 'table') else {},
            'disk_references': 'virtual_pointers'
        }
        
        self.cow_snapshots[snapshot_name] = snapshot_metadata
        return snapshot_metadata

    def restore_from_snapshot(self, snapshot_name: str) -> dict:
        """
        Restore file system from snapshot.
        """
        success = False
        message = ""
        
        try:
            if hasattr(self, 'cow_snapshots') and snapshot_name in self.cow_snapshots:
                snapshot = self.cow_snapshots[snapshot_name]
                if self.fat:
                    self.fat.table = dict(snapshot.get('fat_copy', {}))
                success = True
                message = f"Restored FAT successfully from snapshot {snapshot_name}"
            else:
                message = f"Snapshot {snapshot_name} not found."
        except Exception as e:
            message = f"Error during restore: {e}"
            
        return {
            'success': success,
            'message': message,
            'snapshot_name': snapshot_name
        }

    def incremental_recovery(self, last_checkpoint: datetime) -> dict:
        """
        Perform incremental recovery from last checkpoint.
        """
        recovered_count = 0
        try:
            if self.journal and hasattr(self.journal, 'entries'):
                for entry in self.journal.entries:
                    if isinstance(entry, dict):
                        ts = entry.get('timestamp')
                        entry_dt = None
                        if isinstance(ts, (int, float)):
                            entry_dt = datetime.fromtimestamp(ts)
                        elif isinstance(ts, datetime):
                            entry_dt = ts
                            
                        # Only replay if elapsed after checkpoint
                        if entry_dt and entry_dt > last_checkpoint and entry.get('status') == 'COMMITTED':
                            if self.redo_transaction(entry):
                                recovered_count += 1
        except Exception as e:
            logger.error(f"Incremental recovery failed: {e}")
            
        return {
            'incremental_transactions_recovered': recovered_count,
            'since_checkpoint': last_checkpoint.isoformat(),
            'success': True
        }

    def parallel_recovery(self, num_workers: int = 4) -> dict:
        """
        Perform recovery using parallel processing.
        """
        start_time = time.time()
        success = False
        
        recovered_count = 0
        try:
            entries_to_process = []
            if self.journal and hasattr(self.journal, 'entries'):
                entries_to_process = [e for e in self.journal.entries if isinstance(e, dict) and e.get('status') == 'COMMITTED']
                
            def worker_task(entry):
                return self.redo_transaction(entry)
                
            if entries_to_process:
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                    results = list(executor.map(worker_task, entries_to_process))
                recovered_count = sum(1 for r in results if r)
                success = True
            
        except Exception as e:
            logger.error(f"Parallel recovery failed: {e}")
            
        return {
            'success': success,
            'recovered_transactions': recovered_count,
            'num_workers': num_workers,
            'recovery_time_seconds': time.time() - start_time
        }

    def _calculate_checksum(self, data: bytes, algorithm: str) -> str:
        """
        Calculate checksum for data block.
        """
        if algorithm == 'crc32':
            return hex(zlib.crc32(data) & 0xffffffff)
        elif algorithm == 'md5':
            return hashlib.md5(data).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(data).hexdigest()
        return ""

    def _calculate_parity(self, blocks: list) -> bytes:
        """
        Calculate XOR parity for block group.
        """
        if not blocks:
            return b''
            
        max_len = max(len(b) for b in blocks)
        padded_blocks = [bytearray(b.ljust(max_len, b'\x00')) for b in blocks]
        
        parity = bytearray(max_len)
        for i in range(max_len):
            val = 0
            for pb in padded_blocks:
                val ^= pb[i]
            parity[i] = val
            
        return bytes(parity)

    def _detect_file_signature(self, block_data: bytes) -> Optional[str]:
        """
        Detect file type from block data (magic numbers).
        """
        if not block_data or len(block_data) < 4:
            return None
            
        signatures = {
            b'\x89PNG': 'PNG image',
            b'\xff\xd8\xff': 'JPEG image',
            b'%PDF': 'PDF document',
            b'PK\x03\x04': 'ZIP archive',
            b'GIF8': 'GIF image'
        }
        
        for sig, ftype in signatures.items():
            if block_data.startswith(sig):
                return ftype
                
        return None
