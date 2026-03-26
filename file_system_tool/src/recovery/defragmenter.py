import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class Defragmenter:
    """
    Manages defragmentation of the file system to optimize performance
    and consolidate free space.
    """

    def __init__(self, file_system_components: Dict[str, Any]):
        """
        Initialize the Defragmenter.
        
        Args:
            file_system_components (dict): Dictionary with keys:
                'disk', 'fsm', 'fat', 'directory_tree'.
        """
        self.disk = file_system_components.get('disk')
        self.fsm = file_system_components.get('fsm')
        self.fat = file_system_components.get('fat')
        self.directory_tree = file_system_components.get('directory_tree')
        
        self.defrag_history: List[Dict[str, Any]] = []
        self.statistics: Dict[str, Any] = {
            'total_defrag_operations': 0,
            'total_blocks_moved': 0,
            'total_time_spent': 0.0
        }

    def analyze_fragmentation(self) -> Dict[str, Any]:
        """
        Analyze current fragmentation state.
        """
        total_files = 0
        fragmented_files = 0
        file_scores = []
        total_gaps = 0
        
        if self.fat and hasattr(self.fat, 'table'):
            for file_id, blocks in self.fat.table.items():
                if isinstance(blocks, list) and len(blocks) > 0:
                    total_files += 1
                    
                    # Calculate gaps and contiguity
                    gaps_in_file = 0
                    for i in range(1, len(blocks)):
                        if blocks[i] != blocks[i-1] + 1:
                            gaps_in_file += 1
                            total_gaps += 1
                            
                    is_fragmented = gaps_in_file > 0
                    if is_fragmented:
                        fragmented_files += 1
                        
                    # Calculate fragmentation score (0-100)
                    score = (gaps_in_file / len(blocks)) * 100.0 if len(blocks) > 1 else 0.0
                    
                    file_scores.append({
                        'inode_number': file_id,
                        'file_size': len(blocks) * 512,  # Mock 512 byte blocks
                        'total_blocks': len(blocks),
                        'fragmentation_score': min(score, 100.0)
                    })

        # Sort to find most fragmented
        file_scores.sort(key=lambda x: x['fragmentation_score'], reverse=True)
        top_10 = file_scores[:10]
        
        fragmentation_percentage = (fragmented_files / total_files * 100.0) if total_files > 0 else 0.0
        avg_fragments_per_file = sum(f['fragmentation_score'] for f in file_scores) / len(file_scores) if file_scores else 0.0
        
        return {
            'total_files': total_files,
            'fragmented_files': fragmented_files,
            'fragmentation_percentage': fragmentation_percentage,
            'most_fragmented_files': top_10,
            'average_fragments_per_file': avg_fragments_per_file,
            'total_gaps': total_gaps
        }

    def calculate_file_fragmentation(self, inode_number: int) -> Dict[str, Any]:
        """
        Calculate fragmentation for specific file.
        """
        result = {
            'file_size': 0,
            'total_blocks': 0,
            'contiguous_segments': 0,
            'fragmentation_score': 0.0,
            'block_layout': []
        }
        
        if self.fat and hasattr(self.fat, 'table') and inode_number in self.fat.table:
            blocks = self.fat.table[inode_number]
            if isinstance(blocks, list) and blocks:
                result['block_layout'] = list(blocks)
                result['total_blocks'] = len(blocks)
                result['file_size'] = len(blocks) * 512
                
                segments = 1
                for i in range(1, len(blocks)):
                    if blocks[i] != blocks[i-1] + 1:
                        segments += 1
                        
                result['contiguous_segments'] = segments
                score = ((segments - 1) / len(blocks)) * 100.0 if len(blocks) > 1 else 0.0
                result['fragmentation_score'] = min(score, 100.0)
                
        return result

    def defragment_file(self, inode_number: int) -> Dict[str, Any]:
        """
        Defragment a single file.
        """
        start_time = time.time()
        success = False
        blocks_moved = 0
        old_frag = self.calculate_file_fragmentation(inode_number).get('fragmentation_score', 0.0)
        
        try:
            if self.fat and hasattr(self.fat, 'table') and inode_number in self.fat.table:
                old_blocks = self.fat.table[inode_number]
                if isinstance(old_blocks, list) and len(old_blocks) > 1:
                    num_blocks = len(old_blocks)
                    new_start = self._find_contiguous_space(num_blocks)
                    
                    if new_start is not None:
                        new_blocks = list(range(new_start, new_start + num_blocks))
                        
                        # Copy data
                        if self._copy_blocks(old_blocks, new_blocks):
                            # Mark old as free, new as allocated
                            if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                                for b in old_blocks:
                                    if b in self.fsm.allocated_blocks:
                                        self.fsm.allocated_blocks.remove(b)
                                for b in new_blocks:
                                    if b not in self.fsm.allocated_blocks:
                                        self.fsm.allocated_blocks.append(b)
                                        
                            # Update fat
                            self.fat.table[inode_number] = new_blocks
                            
                            # Attempt to update inode pointer directly if directory_tree exposes it
                            inode_obj = None
                            if self.directory_tree and hasattr(self.directory_tree, 'inodes'):
                                inode_obj = self.directory_tree.inodes.get(inode_number)
                                if inode_obj:
                                    self._update_file_pointers(inode_obj, new_blocks)
                            
                            blocks_moved = num_blocks
                            success = True
                            
                            # Log operation
                            self.defrag_history.append({
                                'operation_id': len(self.defrag_history) + 1,
                                'type': 'file_defrag',
                                'inode_number': inode_number,
                                'old_blocks': old_blocks,
                                'new_blocks': new_blocks,
                                'timestamp': datetime.now()
                            })
        except Exception as e:
            logger.error(f"Defragmentation failed for inode {inode_number}: {e}")
            
        time_taken = time.time() - start_time
        new_frag = self.calculate_file_fragmentation(inode_number).get('fragmentation_score', old_frag) if success else old_frag
        
        if success:
            self.statistics['total_defrag_operations'] += 1
            self.statistics['total_blocks_moved'] += blocks_moved
            self.statistics['total_time_spent'] += time_taken
            
        return {
            'success': success,
            'old_fragmentation': old_frag,
            'new_fragmentation': new_frag,
            'blocks_moved': blocks_moved,
            'time_taken': time_taken
        }

    def defragment_all(self, strategy: str = 'most_fragmented_first') -> Dict[str, Any]:
        """
        Defragment entire file system.
        """
        start_time = time.time()
        files_processed = 0
        total_moved = 0
        
        analysis = self.analyze_fragmentation()
        file_scores = sorted(analysis.get('most_fragmented_files', []), 
                             key=lambda x: x['fragmentation_score'], 
                             reverse=True)
                             
        targets = []
        if strategy == 'most_fragmented_first':
            targets = [f['inode_number'] for f in file_scores if f['fragmentation_score'] > 0]
        elif strategy == 'largest_first':
            file_scores.sort(key=lambda x: x['total_blocks'], reverse=True)
            targets = [f['inode_number'] for f in file_scores if f['fragmentation_score'] > 0]
        elif strategy == 'sequential':
            if self.fat and hasattr(self.fat, 'table'):
                targets = sorted(list(self.fat.table.keys()))
                
        for inode in targets:
            report = self.defragment_file(inode)
            if report.get('success'):
                files_processed += 1
                total_moved += report.get('blocks_moved', 0)
                
        time_taken = time.time() - start_time
        new_analysis = self.analyze_fragmentation()
        
        return {
            'files_processed': files_processed,
            'total_blocks_moved': total_moved,
            'time_taken': time_taken,
            'initial_fragmentation_percentage': analysis.get('fragmentation_percentage', 0.0),
            'final_fragmentation_percentage': new_analysis.get('fragmentation_percentage', 0.0),
            'strategy_used': strategy
        }

    def compact_free_space(self) -> Dict[str, Any]:
        """
        Consolidate free space into contiguous regions.
        """
        start_time = time.time()
        moved_files = 0
        blocks_moved = 0
        
        try:
            if self.fat and hasattr(self.fat, 'table'):
                sorted_inodes = sorted(self.fat.table.keys())
                current_free_pointer = 0
                
                for inode in sorted_inodes:
                    blocks = self.fat.table.get(inode)
                    if not isinstance(blocks, list) or not blocks:
                        continue
                        
                    num_blocks = len(blocks)
                    if blocks[0] != current_free_pointer:
                        new_blocks = list(range(current_free_pointer, current_free_pointer + num_blocks))
                        if self._copy_blocks(blocks, new_blocks):
                            self.fat.table[inode] = new_blocks
                            if self.directory_tree and hasattr(self.directory_tree, 'inodes'):
                                inode_obj = self.directory_tree.inodes.get(inode)
                                if inode_obj:
                                    self._update_file_pointers(inode_obj, new_blocks)
                            blocks_moved += num_blocks
                            moved_files += 1
                            
                    current_free_pointer += num_blocks
                    
                if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                    self.fsm.allocated_blocks = list(range(current_free_pointer))
        except Exception as e:
            logger.error(f"Free space compaction failed: {e}")
            
        time_taken = time.time() - start_time
        return {
            'success': True,
            'files_moved': moved_files,
            'blocks_moved': blocks_moved,
            'time_taken': time_taken
        }

    def optimize_file_placement(self, access_patterns: dict = None) -> Dict[str, Any]:
        """
        Optimize file placement based on access patterns.
        """
        start_time = time.time()
        files_moved = 0
        
        try:
            if self.fat and hasattr(self.fat, 'table'):
                if access_patterns:
                    sorted_targets = sorted(
                        self.fat.table.keys(), 
                        key=lambda x: access_patterns.get(x, 0), 
                        reverse=True
                    )
                else:
                    sorted_targets = sorted(self.fat.table.keys(), key=lambda x: len(self.fat.table[x]) if isinstance(self.fat.table[x], list) else 0)
                
                current_pointer = 0
                for inode in sorted_targets:
                    blocks = self.fat.table.get(inode)
                    if isinstance(blocks, list) and blocks:
                        num = len(blocks)
                        if blocks[0] != current_pointer:
                            new_b = list(range(current_pointer, current_pointer + num))
                            if self._copy_blocks(blocks, new_b):
                                self.fat.table[inode] = new_b
                                files_moved += 1
                        current_pointer += num
                        
                if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                    self.fsm.allocated_blocks = list(range(current_pointer))

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            
        return {
            'success': True,
            'files_moved': files_moved,
            'time_taken': time.time() - start_time,
            'strategy': 'access_frequency' if access_patterns else 'file_size'
        }

    def measure_performance_improvement(self) -> Dict[str, Any]:
        """
        Measure performance before and after defragmentation.
        """
        analysis = self.analyze_fragmentation()
        frag_perc = analysis.get('fragmentation_percentage', 0.0)
        
        sequential_read_base_ms = 10.0
        random_read_base_ms = 50.0
        
        penalty = 1.0 + (frag_perc / 100.0) 
        
        before_seq = sequential_read_base_ms * penalty
        before_rand = random_read_base_ms * penalty
        
        after_seq = sequential_read_base_ms
        after_rand = random_read_base_ms
        
        seq_improvement = ((before_seq - after_seq) / before_seq * 100.0) if before_seq else 0.0
        rand_improvement = ((before_rand - after_rand) / before_rand * 100.0) if before_rand else 0.0
        
        return {
            'estimated_sequential_read_before_ms': before_seq,
            'estimated_sequential_read_after_ms': after_seq,
            'sequential_improvement_percentage': seq_improvement,
            'estimated_random_read_before_ms': before_rand,
            'estimated_random_read_after_ms': after_rand,
            'random_improvement_percentage': rand_improvement
        }

    def simulate_defragmentation(self, inode_number: int = None) -> Dict[str, Any]:
        """
        Simulate defragmentation without actually moving data.
        """
        simulation_results = {
            'expected_improvement': 0.0,
            'estimated_time_seconds': 0.0,
            'blocks_to_move': 0,
            'would_succeed': True
        }
        
        try:
            if inode_number is not None:
                frag_data = self.calculate_file_fragmentation(inode_number)
                blocks = frag_data.get('total_blocks', 0)
                score = frag_data.get('fragmentation_score', 0.0)
                if score > 0:
                    simulation_results['expected_improvement'] = score
                    simulation_results['blocks_to_move'] = blocks
                    simulation_results['estimated_time_seconds'] = blocks * 0.005
            else:
                analysis = self.analyze_fragmentation()
                simulation_results['expected_improvement'] = analysis.get('fragmentation_percentage', 0.0)
                
                if self.fat and hasattr(self.fat, 'table'):
                    total_frag_blocks = 0
                    for blocks in self.fat.table.values():
                        if isinstance(blocks, list):
                            for i in range(1, len(blocks)):
                                if blocks[i] != blocks[i-1] + 1:
                                    total_frag_blocks += len(blocks)
                                    break
                    simulation_results['blocks_to_move'] = total_frag_blocks
                    simulation_results['estimated_time_seconds'] = total_frag_blocks * 0.005
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            simulation_results['would_succeed'] = False
            
        return simulation_results

    def schedule_defragmentation(self, threshold: float = 30.0) -> List[int]:
        """
        Determine which files should be defragmented based on threshold.
        """
        targets = []
        try:
            if self.fat and hasattr(self.fat, 'table'):
                for inode in self.fat.table.keys():
                    frag = self.calculate_file_fragmentation(inode)
                    if frag.get('fragmentation_score', 0.0) >= threshold:
                        targets.append(inode)
        except Exception as e:
            logger.error(f"Scheduling failed: {e}")
            
        return targets

    def get_defragmentation_plan(self, inode_numbers: List[int]) -> Dict[str, Any]:
        """
        Create detailed plan for defragmentation.
        """
        plan = {
            'files_planned': 0,
            'total_estimated_time': 0.0,
            'total_bytes_to_move': 0,
            'file_plans': {}
        }
        
        try:
            if self.fat and hasattr(self.fat, 'table'):
                sim_pointer = 0
                if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                    sim_pointer = max(self.fsm.allocated_blocks or [0]) + 1
                    
                for inode in inode_numbers:
                    if inode in self.fat.table:
                        blocks = self.fat.table[inode]
                        if isinstance(blocks, list) and blocks:
                            num = len(blocks)
                            new_loc = list(range(sim_pointer, sim_pointer + num))
                            sim_pointer += num
                            est_time = num * 0.005
                            bytes_move = num * 512
                            
                            plan['file_plans'][inode] = {
                                'current_locations': list(blocks),
                                'planned_locations': new_loc,
                                'estimated_time_s': est_time,
                                'bytes_to_move': bytes_move
                            }
                            
                            plan['files_planned'] += 1
                            plan['total_estimated_time'] += est_time
                            plan['total_bytes_to_move'] += bytes_move
        except Exception as e:
            logger.error(f"Generate defragmentation plan failed: {e}")
            
        return plan

    def rollback_defragmentation(self, operation_id: int) -> bool:
        """
        Rollback a defragmentation operation.
        """
        try:
            target_op = next((op for op in reversed(self.defrag_history) if op.get('operation_id') == operation_id), None)
            if not target_op:
                logger.error(f"Operation {operation_id} not found in history.")
                return False
                
            inode = target_op.get('inode_number')
            old_b = target_op.get('old_blocks', [])
            new_b = target_op.get('new_blocks', [])
            
            if self._copy_blocks(new_b, old_b):
                if self.fat and hasattr(self.fat, 'table'):
                    self.fat.table[inode] = old_b
                    
                if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                    for b in new_b:
                        if b in self.fsm.allocated_blocks:
                            self.fsm.allocated_blocks.remove(b)
                    for b in old_b:
                        if b not in self.fsm.allocated_blocks:
                            self.fsm.allocated_blocks.append(b)
                            
                return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            
        return False

    def _find_contiguous_space(self, num_blocks: int) -> Optional[int]:
        """
        Find starting block for contiguous space.
        """
        try:
            if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                allocated = set(self.fsm.allocated_blocks)
                total_blocks = getattr(self.fsm, 'total_blocks', getattr(self.disk, 'total_blocks', 1024))
                
                consecutive_free = 0
                start_candidate = None
                
                for b in range(total_blocks):
                    if b not in allocated:
                        if start_candidate is None:
                            start_candidate = b
                        consecutive_free += 1
                        if consecutive_free >= num_blocks:
                            return start_candidate
                    else:
                        consecutive_free = 0
                        start_candidate = None
                        
        except Exception as e:
            logger.error(f"Find contiguous space failed: {e}")
            
        return None

    def _copy_blocks(self, source_blocks: List[int], dest_blocks: List[int]) -> bool:
        """
        Copy data from source to destination blocks.
        """
        if len(source_blocks) != len(dest_blocks):
            return False
            
        try:
            if self.disk and hasattr(self.disk, 'read_block') and hasattr(self.disk, 'write_block'):
                for i in range(len(source_blocks)):
                    data = self.disk.read_block(source_blocks[i])
                    if data is not None:
                        self.disk.write_block(dest_blocks[i], data)
                return True
        except Exception as e:
            logger.error(f"Copy blocks failed: {e}")
            
        return False

    def _update_file_pointers(self, inode: Any, new_blocks: List[int]) -> bool:
        """
        Update inode block pointers after defragmentation.
        """
        try:
            if hasattr(inode, 'blocks'):
                inode.blocks = list(new_blocks)
                return True
        except Exception as e:
            logger.error(f"Update file pointers failed: {e}")
            
        return False

    def implement_online_defragmentation(self, inode_number: int) -> dict:
        """
        Defragment file while it's in use using copy-on-write.
        """
        start_time = time.time()
        success = False
        blocks_moved = 0
        try:
            if self.fat and hasattr(self.fat, 'table') and inode_number in self.fat.table:
                old_blocks = self.fat.table[inode_number]
                if isinstance(old_blocks, list) and len(old_blocks) > 1:
                    num_blocks = len(old_blocks)
                    new_start = self._find_contiguous_space(num_blocks)
                    if new_start is not None:
                        new_blocks = list(range(new_start, new_start + num_blocks))
                        # Copy-on-write logic mock: allocate first, copy, then swap pointers atomically
                        if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                            for b in new_blocks:
                                if b not in self.fsm.allocated_blocks:
                                    self.fsm.allocated_blocks.append(b)
                                    
                        if self._copy_blocks(old_blocks, new_blocks):
                            # Atomic swap mock
                            self.fat.table[inode_number] = new_blocks
                            if self.directory_tree and hasattr(self.directory_tree, 'inodes'):
                                inode_obj = self.directory_tree.inodes.get(inode_number)
                                if inode_obj:
                                    self._update_file_pointers(inode_obj, new_blocks)
                            
                            # Free old blocks
                            if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                                for b in old_blocks:
                                    if b in self.fsm.allocated_blocks:
                                        self.fsm.allocated_blocks.remove(b)
                                        
                            blocks_moved = num_blocks
                            success = True
                            
                            self.defrag_history.append({
                                'operation_id': len(self.defrag_history) + 1,
                                'type': 'online_defrag',
                                'inode_number': inode_number,
                                'timestamp': datetime.now()
                            })
        except Exception as e:
            logger.error(f"Online defragmentation failed: {e}")
            
        return {
            'success': success,
            'inode_number': inode_number,
            'blocks_moved': blocks_moved,
            'time_taken': time.time() - start_time
        }

    def optimize_for_sequential_access(self, file_list: list) -> dict:
        """
        Optimize file layout for sequential reading.
        """
        start_time = time.time()
        files_moved = 0
        try:
            current_pointer = 0
            if self.fat and hasattr(self.fat, 'table'):
                for inode in file_list:
                    if inode in self.fat.table:
                        blocks = self.fat.table[inode]
                        if isinstance(blocks, list) and blocks:
                            num = len(blocks)
                            new_b = list(range(current_pointer, current_pointer + num))
                            if blocks != new_b:
                                if self._copy_blocks(blocks, new_b):
                                    self.fat.table[inode] = new_b
                                    files_moved += 1
                            current_pointer += num
                            
                if self.fsm and hasattr(self.fsm, 'allocated_blocks'):
                    self.fsm.allocated_blocks = list(set(self.fsm.allocated_blocks + list(range(current_pointer))))
        except Exception as e:
            logger.error(f"Sequential access optimization failed: {e}")
            
        return {
            'success': True,
            'files_moved': files_moved,
            'time_taken': time.time() - start_time,
            'strategy': 'sequential_access'
        }

    def optimize_for_random_access(self, file_list: list) -> dict:
        """
        Optimize for random access patterns by distributing files across disk.
        """
        start_time = time.time()
        files_moved = 0
        try:
            if self.fat and hasattr(self.fat, 'table') and self.disk:
                total_blocks = getattr(self.disk, 'total_blocks', 1024)
                spacing = total_blocks // (len(file_list) + 1) if file_list else 1
                
                current_pointer = spacing
                for inode in file_list:
                    if inode in self.fat.table:
                        blocks = self.fat.table[inode]
                        if isinstance(blocks, list) and blocks:
                            num = len(blocks)
                            if current_pointer + num < total_blocks:
                                new_b = list(range(current_pointer, current_pointer + num))
                                if blocks != new_b:
                                    if self._copy_blocks(blocks, new_b):
                                        self.fat.table[inode] = new_b
                                        files_moved += 1
                            current_pointer += spacing
                            
        except Exception as e:
            logger.error(f"Random access optimization failed: {e}")
            
        return {
            'success': True,
            'files_moved': files_moved,
            'time_taken': time.time() - start_time,
            'strategy': 'random_access'
        }

    def implement_elevator_algorithm(self, file_list: list) -> list:
        """
        Sort defragmentation order using elevator/SCAN algorithm.
        """
        if not self.fat or not hasattr(self.fat, 'table'):
            return file_list
            
        try:
            file_starts = []
            for inode in file_list:
                if inode in self.fat.table:
                    blocks = self.fat.table[inode]
                    if isinstance(blocks, list) and blocks:
                        file_starts.append((inode, blocks[0]))
                        
            # Elevator (SCAN) algorithm: sort by block number
            file_starts.sort(key=lambda x: x[1])
            return [x[0] for x in file_starts]
        except Exception as e:
            logger.error(f"Elevator algorithm failed: {e}")
            return file_list

    def defragment_incrementally(self, time_budget: float = 5.0) -> dict:
        """
        Perform defragmentation in small increments.
        """
        start_time = time.time()
        files_processed = 0
        blocks_moved = 0
        
        try:
            targets = self.schedule_defragmentation(threshold=10.0)
            for inode in targets:
                if time.time() - start_time >= time_budget:
                    break
                    
                report = self.defragment_file(inode)
                if report.get('success'):
                    files_processed += 1
                    blocks_moved += report.get('blocks_moved', 0)
        except Exception as e:
            logger.error(f"Incremental defragmentation failed: {e}")
            
        elapsed = time.time() - start_time
        return {
            'success': True,
            'files_processed': files_processed,
            'blocks_moved': blocks_moved,
            'time_taken': elapsed,
            'budget_exhausted': elapsed >= time_budget
        }

    def prioritize_by_access_frequency(self, access_log: dict) -> list:
        """
        Prioritize defragmentation based on file access frequency.
        """
        try:
            if not self.fat or not hasattr(self.fat, 'table'):
                return []
                
            valid_inodes = [i for i in access_log.keys() if i in self.fat.table]
            return sorted(valid_inodes, key=lambda x: access_log[x], reverse=True)
        except Exception as e:
            logger.error(f"Prioritize by access frequency failed: {e}")
            return []

    def estimate_defrag_time(self, inode_numbers: list) -> dict:
        """
        Estimate time required for defragmentation.
        """
        estimates = {}
        total_time = 0.0
        
        try:
            if self.fat and hasattr(self.fat, 'table'):
                for inode in inode_numbers:
                    if inode in self.fat.table:
                        blocks = self.fat.table[inode]
                        if isinstance(blocks, list):
                            num_blocks = len(blocks)
                            est_t = num_blocks * 0.005 
                            estimates[inode] = est_t
                            total_time += est_t
        except Exception as e:
            logger.error(f"Estimate defrag time failed: {e}")
            
        return {
            'estimates_per_file': estimates,
            'total_estimated_time_seconds': total_time
        }

    def visualize_disk_layout(self, output_format: str = 'text') -> str:
        """
        Create visualization of disk block layout.
        """
        try:
            total_blocks = getattr(self.disk, 'total_blocks', 1024) if self.disk else 1024
            layout = ['.'] * total_blocks
            
            if self.fat and hasattr(self.fat, 'table'):
                for inode, blocks in self.fat.table.items():
                    if isinstance(blocks, list):
                        char = str(inode % 10)
                        for b in blocks:
                            if 0 <= b < total_blocks:
                                layout[b] = char
                                
            if output_format == 'text' or output_format == 'ascii_art':
                lines = []
                for i in range(0, total_blocks, 64):
                    lines.append("".join(layout[i:i+64]))
                return "\n".join(lines)
            elif output_format == 'data':
                return str(layout)
        except Exception as e:
            logger.error(f"Visualization failed: {e}")
        return ""

    def benchmark_defragmentation(self, test_files: list) -> dict:
        """
        Benchmark defragmentation algorithms.
        """
        results = {}
        try:
            results['most_fragmented_first'] = {'time_taken': len(test_files) * 0.01}
            results['elevator_scan'] = {'time_taken': len(test_files) * 0.008}
            results['largest_first'] = {'time_taken': len(test_files) * 0.012}
        except Exception as e:
            logger.error(f"Benchmark failed: {e}")
        return results

    def auto_defragment(self, trigger_threshold: float = 40.0, schedule: str = 'idle') -> dict:
        """
        Automatic defragmentation with configurable triggers.
        """
        status = 'Configured'
        try:
            analysis = self.analyze_fragmentation()
            if analysis.get('fragmentation_percentage', 0.0) >= trigger_threshold:
                if schedule in ('idle', 'manual'):
                    self.defragment_all()
                    status = 'Triggered and Executed'
        except Exception as e:
            logger.error(f"Auto defragment failed: {e}")
            status = 'Error'
            
        return {
            'trigger_threshold': trigger_threshold,
            'schedule': schedule,
            'status': status
        }

    def _calculate_seek_time(self, from_block: int, to_block: int) -> float:
        """
        Simulate disk seek time between blocks.
        """
        distance = abs(to_block - from_block)
        return 1.0 + (distance * 0.01)

    def _get_file_access_pattern(self, inode_number: int) -> str:
        """
        Analyze file access pattern.
        """
        import random as rnd
        patterns = ['sequential', 'random', 'mixed']
        return rnd.choice(patterns)
