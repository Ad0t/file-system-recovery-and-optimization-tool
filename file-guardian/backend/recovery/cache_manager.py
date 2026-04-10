import logging
import time
import copy
from typing import Dict, Any, List, Optional, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages caching of disk blocks to optimize read/write performance.
    Supports LRU, LFU, and FIFO caching strategies.
    """

    def __init__(self, disk: Any, cache_size: int = 24, strategy: str = 'LRU'):
        """
        Initialize the CacheManager.
        
        Args:
            disk: Reference to disk component.
            cache_size (int): Maximum number of blocks to cache.
            strategy (str): 'LRU', 'LFU', or 'FIFO'
        """
        self.disk = disk
        self.cache_size = cache_size
        self.strategy = strategy
        
        self.cache_data: Dict[int, bytes] = {}
        self.access_order: OrderedDict[int, None] = OrderedDict()
        self.access_frequency: Dict[int, int] = {}
        
        # New advanced tracking states
        self.dirty_blocks: set = set()
        self.access_history: List[int] = []
        self.entry_timestamps: Dict[int, float] = {}
        
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.eviction_count: int = 0

    def get(self, block_num: int) -> Optional[bytes]:
        """
        Get block from cache or disk.
        """
        hit = block_num in self.cache_data
        self._track_access(block_num, hit)
        
        if hit:
            self.cache_hits += 1
            if self.strategy == 'LRU':
                self._update_lru(block_num)
            elif self.strategy == 'LFU':
                self._update_lfu(block_num)
            return self.cache_data[block_num]
            
        self.cache_misses += 1
        
        if not self.disk or not hasattr(self.disk, 'read_block'):
            logger.error(f"Cannot fetch block {block_num}: invalid disk reference")
            return None
            
        try:
            data = self.disk.read_block(block_num)
            if data is not None:
                self.put(block_num, data)
                return data
        except Exception as e:
            logger.error(f"Failed to fetch block {block_num} from disk: {e}")
            
        return None

    def put(self, block_num: int, data: bytes) -> bool:
        """
        Add block to cache.
        """
        if self.cache_size <= 0:
            return False
            
        if block_num in self.cache_data:
            self.cache_data[block_num] = data
            if self.strategy == 'LRU':
                self._update_lru(block_num)
            elif self.strategy == 'LFU':
                self._update_lfu(block_num)
            self.entry_timestamps[block_num] = time.time()
            return True
            
        if len(self.cache_data) >= self.cache_size:
            evict_candidate = self._get_eviction_candidate()
            if evict_candidate is not None:
                self.invalidate(evict_candidate)
                self.eviction_count += 1
                
        self.cache_data[block_num] = data
        if self.strategy in ('LRU', 'FIFO'):
            self.access_order[block_num] = None
        elif self.strategy == 'LFU':
            self.access_frequency[block_num] = 1
            
        self.entry_timestamps[block_num] = time.time()
        return True

    def evict_lru(self) -> Optional[int]:
        """
        Evict least recently used block.
        """
        if not self.access_order:
            return None
        try:
            oldest_block, _ = self.access_order.popitem(last=False)
            return oldest_block
        except KeyError:
            return None

    def evict_fifo(self) -> Optional[int]:
        """
        Evict first-in block. Shares mechanics with LRU base ordered dict.
        """
        return self.evict_lru()

    def evict_lfu(self) -> Optional[int]:
        """
        Evict least frequently used block. If tie, use LRU.
        """
        if not self.cache_data:
            return None
            
        min_freq = float('inf')
        candidates = []
        
        for b, freq in self.access_frequency.items():
            if freq < min_freq:
                min_freq = freq
                candidates = [b]
            elif freq == min_freq:
                candidates.append(b)
                
        if len(candidates) == 1:
            return candidates[0]
            
        for b in self.access_order.keys():
            if b in candidates:
                return b
                
        return candidates[0] if candidates else None

    def clear_cache(self) -> None:
        """
        Clear all cached data.
        """
        self.cache_data.clear()
        self.access_order.clear()
        self.access_frequency.clear()
        self.dirty_blocks.clear()
        self.access_history.clear()
        self.entry_timestamps.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.eviction_count = 0

    def get_hit_rate(self) -> float:
        """
        Calculate cache hit rate percentage.
        """
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100.0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Return comprehensive cache statistics.
        """
        sorted_freq = sorted(self.access_frequency.items(), key=lambda x: x[1], reverse=True)
        top_10 = sorted_freq[:10]
        
        return {
            'cache_size': len(self.cache_data),
            'max_cache_size': self.cache_size,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': self.get_hit_rate(),
            'most_accessed_blocks': top_10,
            'eviction_count': self.eviction_count,
            'strategy': self.strategy,
            'cached_blocks': self.get_cached_blocks(),
            'access_frequency': dict(self.access_frequency),
        }

    def prefetch(self, block_nums: List[int]) -> int:
        """
        Prefetch multiple blocks into cache.
        """
        success_count = 0
        if not self.disk or not hasattr(self.disk, 'read_block'):
            return 0
            
        for b in block_nums:
            if b not in self.cache_data:
                try:
                    data = self.disk.read_block(b)
                    if data is not None:
                        if self.put(b, data):
                            success_count += 1
                except Exception as e:
                    logger.error(f"Prefetch failed for block {b}: {e}")
            else:
                success_count += 1
                
        return success_count

    def invalidate(self, block_num: int) -> bool:
        """
        Remove specific block from cache.
        """
        if block_num in self.cache_data:
            del self.cache_data[block_num]
            self.access_order.pop(block_num, None)
            self.access_frequency.pop(block_num, None)
            self.entry_timestamps.pop(block_num, None)
            if block_num in self.dirty_blocks:
                self.dirty_blocks.remove(block_num)
            return True
        return False

    def resize_cache(self, new_size: int) -> bool:
        """
        Change cache size dynamically.
        """
        if new_size < 0:
            return False
            
        self.cache_size = new_size
        
        while len(self.cache_data) > self.cache_size:
            candidate = self._get_eviction_candidate()
            if candidate is not None:
                self.invalidate(candidate)
                self.eviction_count += 1
            else:
                break
                
        return True

    def set_strategy(self, new_strategy: str) -> bool:
        """
        Change caching strategy.
        """
        valid_strategies = ['LRU', 'LFU', 'FIFO']
        if new_strategy not in valid_strategies:
            logger.error(f"Invalid strategy: {new_strategy}")
            return False
            
        if self.strategy == new_strategy:
            return True
            
        self.strategy = new_strategy
        
        self.access_order.clear()
        self.access_frequency.clear()
        
        for k in self.cache_data.keys():
            if self.strategy in ('LRU', 'FIFO'):
                self.access_order[k] = None
            elif self.strategy == 'LFU':
                self.access_frequency[k] = 1
                
        return True

    def get_cached_blocks(self) -> List[int]:
        """
        Return list of block numbers currently in cache.
        """
        if self.strategy in ('LRU', 'FIFO'):
            return list(self.access_order.keys())
        elif self.strategy == 'LFU':
            # Highest read frequency first (educational / heatmap order); tie-break by block id.
            items = [
                (b, self.access_frequency.get(b, 0))
                for b in self.cache_data.keys()
            ]
            items.sort(key=lambda t: (-t[1], t[0]))
            return [b for b, _ in items]
        else:
            return list(self.cache_data.keys())

    def is_cached(self, block_num: int) -> bool:
        """
        Check if block is in cache.
        """
        return block_num in self.cache_data

    def _update_lru(self, block_num: int) -> None:
        """
        Update LRU tracking when block accessed.
        """
        if block_num in self.access_order:
            self.access_order.move_to_end(block_num)
        else:
            self.access_order[block_num] = None

    def _update_lfu(self, block_num: int) -> None:
        """
        Update LFU tracking when block accessed.
        """
        if block_num in self.access_frequency:
            self.access_frequency[block_num] += 1
        else:
            self.access_frequency[block_num] = 1

    def _get_eviction_candidate(self) -> Optional[int]:
        """
        Get next block to evict based on current strategy.
        """
        if self.strategy == 'LRU':
            return self.evict_lru()
        elif self.strategy == 'LFU':
            return self.evict_lfu()
        elif self.strategy == 'FIFO':
            return self.evict_fifo()
        return self.evict_lru()

    # --- ADVANCED CACHE MANAGER METHODS ---



    def predictive_prefetch(self, block_num: int, pattern: str = 'sequential') -> List[int]:
        """
        Predict and prefetch likely next blocks.
        """
        prefetched = []
        if pattern == 'sequential':
            for b in range(block_num + 1, block_num + 6):
                if not self.is_cached(b):
                    prefetched.append(b)
        elif pattern == 'stride':
            stride = 2
            for b in range(block_num + stride, block_num + (stride*4), stride):
                if not self.is_cached(b):
                    prefetched.append(b)
        elif pattern == 'learned':
            prefetched.append(block_num + 10)
            
        if prefetched:
            self.prefetch(prefetched)
        return prefetched

    def analyze_access_pattern(self, window_size: int = 100) -> Dict[str, Any]:
        """
        Analyze recent access patterns.
        """
        recent = self.access_history[-window_size:]
        pattern_type = 'random'
        confidence = 0.5
        suggested = 0
        
        if len(recent) > 5:
            if self._detect_sequential_pattern(recent):
                pattern_type = 'sequential'
                confidence = 0.9
                suggested = 8
            else:
                diffs = [recent[i] - recent[i-1] for i in range(1, len(recent))]
                if len(set(diffs[-5:])) == 1:
                    pattern_type = 'stride'
                    confidence = 0.8
                    suggested = 4
                    
        return {
            'pattern_type': pattern_type,
            'confidence': confidence,
            'suggested_prefetch_size': suggested
        }

    def adaptive_cache_sizing(self, target_hit_rate: float = 0.8) -> int:
        """
        Automatically adjust cache size to achieve target hit rate.
        """
        current_rate = self.get_hit_rate() / 100.0
        if current_rate < target_hit_rate:
            self.resize_cache(int(max(10, self.cache_size * 1.2)))
        elif current_rate > target_hit_rate + 0.1:
            self.resize_cache(int(max(10, self.cache_size * 0.9)))
        return self.cache_size

    def implement_write_through(self, block_num: int, data: bytes) -> bool:
        """
        Write-through cache: write to both cache and disk.
        """
        try:
            if self.disk and hasattr(self.disk, 'write_block'):
                self.disk.write_block(block_num, data)
            self.put(block_num, data)
            return True
        except Exception as e:
            logger.error(f"Write-through failed for block {block_num}: {e}")
            return False

    def implement_write_back(self, block_num: int, data: bytes) -> bool:
        """
        Write-back cache: write to cache only, flush later.
        """
        try:
            self.put(block_num, data)
            self.dirty_blocks.add(block_num)
            return True
        except Exception as e:
            logger.error(f"Write-back failed for block {block_num}: {e}")
            return False

    def flush_dirty_blocks(self) -> int:
        """
        Write all dirty (modified) blocks to disk.
        """
        count = 0
        if self.disk and hasattr(self.disk, 'write_block'):
            to_flush = list(self.dirty_blocks)
            for b in to_flush:
                if b in self.cache_data:
                    try:
                        self.disk.write_block(b, self.cache_data[b])
                        self.dirty_blocks.remove(b)
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to flush dirty block {b}: {e}")
        return count

    def get_dirty_blocks(self) -> List[int]:
        """
        Return list of dirty block numbers.
        """
        return list(self.dirty_blocks)

    def implement_cache_partitioning(self, partitions: Dict[str, float]) -> bool:
        """
        Partition cache for different purposes.
        """
        total_ratio = sum(partitions.values())
        if abs(total_ratio - 1.0) > 0.01:
            logger.error("Partition ratios must sum to 1.0")
            return False
            
        self.partitions = {}
        for name, ratio in partitions.items():
            self.partitions[name] = {
                'max_size': int(self.cache_size * ratio),
                'current_size': 0
            }
        return True

    def benchmark_strategy(self, access_sequence: List[int]) -> Dict[str, float]:
        """
        Benchmark different caching strategies.
        """
        results = {}
        original_strategy = self.strategy
        
        for strat in ['LRU', 'LFU', 'FIFO']:
            self.clear_cache()
            self.set_strategy(strat)
            for b in access_sequence:
                self.get(b)
            results[strat] = self.get_hit_rate()
            
        self.clear_cache()
        self.set_strategy(original_strategy)
            
        return results

    def get_heatmap_data(self) -> Dict[int, int]:
        """
        Get access frequency for all blocks.
        """
        return dict(self.access_frequency)

    def expire_old_entries(self, max_age_seconds: float = 300.0) -> int:
        """
        Remove cache entries older than max_age.
        """
        expired = 0
        now = time.time()
        to_expire = [b for b, ts in self.entry_timestamps.items() if now - ts > max_age_seconds]
        for b in to_expire:
            if self.invalidate(b):
                expired += 1
        return expired

    def clone_cache(self) -> 'CacheManager':
        """
        Create copy of cache manager.
        """
        new_manager = CacheManager(self.disk, self.cache_size, self.strategy)
        new_manager.cache_data = copy.deepcopy(self.cache_data)
        new_manager.access_order = copy.deepcopy(self.access_order)
        new_manager.access_frequency = copy.deepcopy(self.access_frequency)
        new_manager.dirty_blocks = copy.deepcopy(self.dirty_blocks)
        new_manager.entry_timestamps = copy.deepcopy(self.entry_timestamps)
        new_manager.cache_hits = self.cache_hits
        new_manager.cache_misses = self.cache_misses
        new_manager.eviction_count = self.eviction_count
        return new_manager

    def _track_access(self, block_num: int, hit: bool) -> None:
        """
        Track access for analytics.
        """
        self.access_history.append(block_num)
        self.entry_timestamps[block_num] = time.time()
        
        if len(self.access_history) > 10000:
            self.access_history = self.access_history[-5000:]

    def _detect_sequential_pattern(self, recent_accesses: List[int]) -> bool:
        """
        Detect if recent accesses are sequential.
        """
        if len(recent_accesses) < 3:
            return False
            
        sequential_count = 0
        for i in range(1, len(recent_accesses)):
            if recent_accesses[i] == recent_accesses[i-1] + 1:
                sequential_count += 1
                
        return (sequential_count / len(recent_accesses)) > 0.7

    def _calculate_working_set_size(self) -> int:
        """
        Estimate working set size (unique blocks accessed recently).
        """
        recent = self.access_history[-1000:]
        return len(set(recent)) if recent else len(self.cache_data)
