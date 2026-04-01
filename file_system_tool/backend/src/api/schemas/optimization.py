from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class DefragmentationRequest(BaseModel):
    inode_number: Optional[int] = None  # None = defrag all
    strategy: str = "most_fragmented_first"


class DefragmentationReport(BaseModel):
    success: bool
    files_defragmented: int
    fragmentation_before: float
    fragmentation_after: float
    blocks_moved: int
    time_taken: float


class FragmentationAnalysis(BaseModel):
    total_files: int
    fragmented_files: int
    fragmentation_percentage: float
    most_fragmented: List[Dict[str, Any]]


class CacheConfig(BaseModel):
    cache_size: int
    strategy: str  # LRU, LFU, ARC


class CacheStats(BaseModel):
    cache_size: int
    max_cache_size: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    strategy: str
