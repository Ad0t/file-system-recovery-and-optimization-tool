"""
metrics.py - Pydantic schemas for performance metrics and optimization.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# Defragmentation Models
# =============================================================================

class FileFragmentation(BaseModel):
    """Fragmentation info for a single file."""
    inode_number: int = Field(..., description="Inode number")
    file_size: int = Field(..., description="File size in bytes")
    total_blocks: int = Field(..., description="Total blocks used")
    contiguous_segments: int = Field(..., description="Number of contiguous segments")
    fragmentation_score: float = Field(..., description="Fragmentation score 0-100")
    block_layout: List[int] = Field(default_factory=list, description="Block layout")


class FragmentationAnalysisResponse(BaseModel):
    """Response for fragmentation analysis."""
    total_files: int = Field(..., description="Total number of files")
    fragmented_files: int = Field(..., description="Number of fragmented files")
    fragmentation_percentage: float = Field(..., description="Overall fragmentation percentage")
    most_fragmented_files: List[FileFragmentation] = Field(default_factory=list, description="Top fragmented files")
    average_fragments_per_file: float = Field(..., description="Average fragments per file")
    total_gaps: int = Field(..., description="Total gaps across all files")


class DefragFileRequest(BaseModel):
    """Request to defragment a file."""
    inode_number: int = Field(..., description="Inode number to defragment")


class DefragFileResponse(BaseModel):
    """Response for single file defragmentation."""
    success: bool = Field(..., description="Operation success")
    inode_number: int = Field(..., description="Inode number")
    old_fragmentation: float = Field(..., description="Old fragmentation score")
    new_fragmentation: float = Field(..., description="New fragmentation score")
    blocks_moved: int = Field(..., description="Number of blocks moved")
    time_taken: float = Field(..., description="Time taken in seconds")


class DefragAllRequest(BaseModel):
    """Request to defragment all files."""
    strategy: str = Field("most_fragmented_first", description="Strategy: 'most_fragmented_first', 'largest_first', 'sequential'")


class DefragAllResponse(BaseModel):
    """Response for full defragmentation."""
    files_processed: int = Field(..., description="Number of files processed")
    total_blocks_moved: int = Field(..., description="Total blocks moved")
    time_taken: float = Field(..., description="Time taken in seconds")
    initial_fragmentation_percentage: float = Field(..., description="Initial fragmentation")
    final_fragmentation_percentage: float = Field(..., description="Final fragmentation")
    strategy_used: str = Field(..., description="Strategy used")


class CompactResponse(BaseModel):
    """Response for free space compaction."""
    success: bool = Field(..., description="Operation success")
    files_moved: int = Field(..., description="Number of files moved")
    blocks_moved: int = Field(..., description="Number of blocks moved")
    time_taken: float = Field(..., description="Time taken in seconds")


class OptimizationStrategyRequest(BaseModel):
    """Request for file placement optimization."""
    access_patterns: Optional[Dict[int, int]] = Field(None, description="Optional access frequency per inode")


class OptimizationResponse(BaseModel):
    """Response for file placement optimization."""
    success: bool = Field(..., description="Operation success")
    files_moved: int = Field(..., description="Number of files moved")
    time_taken: float = Field(..., description="Time taken in seconds")
    strategy: str = Field(..., description="Strategy used")


class DefragPlanRequest(BaseModel):
    """Request to generate defragmentation plan."""
    inode_numbers: List[int] = Field(..., description="List of inodes to plan for")


class DefragPlanResponse(BaseModel):
    """Response for defragmentation plan."""
    files_planned: int = Field(..., description="Number of files planned")
    total_estimated_time: float = Field(..., description="Estimated time in seconds")
    total_bytes_to_move: int = Field(..., description="Total bytes to move")
    file_plans: Dict[int, Dict[str, Any]] = Field(default_factory=dict, description="Detailed plans per file")


class DefragSimulationResponse(BaseModel):
    """Response for defragmentation simulation."""
    expected_improvement: float = Field(..., description="Expected improvement percentage")
    estimated_time_seconds: float = Field(..., description="Estimated time in seconds")
    blocks_to_move: int = Field(..., description="Number of blocks that would be moved")
    would_succeed: bool = Field(..., description="Whether simulation indicates success")


class ScheduleDefragRequest(BaseModel):
    """Request to schedule defragmentation."""
    threshold: float = Field(30.0, ge=0.0, le=100.0, description="Fragmentation threshold")


class ScheduleDefragResponse(BaseModel):
    """Response for defragmentation scheduling."""
    targets: List[int] = Field(default_factory=list, description="List of inodes that need defragmentation")


class DefragRollbackRequest(BaseModel):
    """Request to rollback defragmentation."""
    operation_id: int = Field(..., description="Operation ID to rollback")


class DefragRollbackResponse(BaseModel):
    """Response for defragmentation rollback."""
    success: bool = Field(..., description="Whether rollback succeeded")


class DiskLayoutVisualizationResponse(BaseModel):
    """Response for disk layout visualization."""
    layout: str = Field(..., description="ASCII representation of disk layout")


# =============================================================================
# Cache Models
# =============================================================================

class CacheConfigRequest(BaseModel):
    """Request to configure cache."""
    cache_size: int = Field(100, ge=1, description="Cache size (number of blocks)")
    strategy: str = Field("LRU", description="Strategy: 'LRU', 'LFU', 'ARC', '2Q'")


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    cache_size: int = Field(..., description="Current cache size")
    max_cache_size: int = Field(..., description="Maximum cache size")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")
    hit_rate: float = Field(..., description="Hit rate percentage")
    most_accessed_blocks: List[tuple] = Field(default_factory=list, description="Top accessed blocks")
    eviction_count: int = Field(..., description="Number of evictions")
    strategy: str = Field(..., description="Current strategy")


class CacheStrategyRequest(BaseModel):
    """Request to change cache strategy."""
    strategy: str = Field(..., description="New strategy: 'LRU', 'LFU', 'ARC', '2Q'")


class PrefetchRequest(BaseModel):
    """Request to prefetch blocks."""
    block_numbers: List[int] = Field(..., description="Blocks to prefetch")


class PrefetchResponse(BaseModel):
    """Response for prefetch operation."""
    success_count: int = Field(..., description="Number of blocks prefetched")


class PredictivePrefetchRequest(BaseModel):
    """Request for predictive prefetch."""
    block_num: int = Field(..., description="Current block number")
    pattern: str = Field("sequential", description="Pattern: 'sequential', 'stride', 'learned'")


class PredictivePrefetchResponse(BaseModel):
    """Response for predictive prefetch."""
    prefetched: List[int] = Field(default_factory=list, description="Blocks prefetched")


class PatternAnalysisResponse(BaseModel):
    """Response for access pattern analysis."""
    pattern_type: str = Field(..., description="Detected pattern: 'random', 'sequential', 'stride'")
    confidence: float = Field(..., description="Confidence level 0-1")
    suggested_prefetch_size: int = Field(..., description="Suggested prefetch size")


class CacheFlushResponse(BaseModel):
    """Response for cache flush."""
    flushed_count: int = Field(..., description="Number of dirty blocks flushed")


class DirtyBlocksResponse(BaseModel):
    """Response for dirty blocks query."""
    dirty_blocks: List[int] = Field(default_factory=list, description="List of dirty block numbers")


# =============================================================================
# Performance Analysis Models
# =============================================================================

class PerformanceMetrics(BaseModel):
    """Current performance metrics."""
    timestamp: float = Field(..., description="Timestamp")
    disk_usage_percentage: float = Field(..., description="Disk usage percentage")
    fragmentation_percentage: float = Field(..., description="Fragmentation percentage")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")
    average_read_time: float = Field(..., description="Average read time")
    average_write_time: float = Field(..., description="Average write time")
    total_operations: int = Field(..., description="Total operations count")
    free_space_percentage: float = Field(..., description="Free space percentage")


class BottleneckResponse(BaseModel):
    """Response for bottleneck analysis."""
    bottlenecks: List[str] = Field(default_factory=list, description="List of bottlenecks")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class PerformanceReportResponse(BaseModel):
    """Response for performance report."""
    report: str = Field(..., description="Formatted performance report")


class BenchmarkResponse(BaseModel):
    """Response for benchmark operations."""
    results: Dict[str, Any] = Field(..., description="Benchmark results")


class ComparisonResponse(BaseModel):
    """Response for performance comparison."""
    comparison: Dict[str, Dict[str, Any]] = Field(..., description="Detailed comparison")


class IOPSCalculationResponse(BaseModel):
    """Response for IOPS calculation."""
    read_iops: float = Field(..., description="Read IOPS")
    write_iops: float = Field(..., description="Write IOPS")
    total_iops: float = Field(..., description="Total IOPS")


class ThroughputResponse(BaseModel):
    """Response for throughput measurement."""
    read_throughput_mbps: float = Field(..., description="Read throughput MB/s")
    write_throughput_mbps: float = Field(..., description="Write throughput MB/s")


class DiskFullPrediction(BaseModel):
    """Response for disk full prediction."""
    estimated_days_until_full: float = Field(..., description="Estimated days until full")
    current_usage_trend_pct_per_day: float = Field(..., description="Usage trend per day")
    confidence_level: str = Field(..., description="Confidence level")


class PerformanceDegradationPrediction(BaseModel):
    """Response for performance degradation prediction."""
    fragmentation_trend: str = Field(..., description="Trend: 'increasing', 'decreasing', 'stable'")
    cache_hit_trend: str = Field(..., description="Trend: 'increasing', 'decreasing', 'stable'")
    prediction: str = Field(..., description="Performance prediction")


class OptimizationRecommendation(BaseModel):
    """Single optimization recommendation."""
    optimization_type: str = Field(..., description="Type of optimization")
    priority: str = Field(..., description="Priority: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'")
    expected_improvement: str = Field(..., description="Expected improvement")
    description: str = Field(..., description="Description of optimization")


class OptimizationRecommendationsResponse(BaseModel):
    """Response for optimization recommendations."""
    recommendations: List[OptimizationRecommendation] = Field(default_factory=list)


class Anomaly(BaseModel):
    """Single anomaly detection."""
    timestamp: float = Field(..., description="Timestamp of anomaly")
    metric: str = Field(..., description="Affected metric")
    value: float = Field(..., description="Anomalous value")
    description: str = Field(..., description="Description of anomaly")


class AnomalyDetectionResponse(BaseModel):
    """Response for anomaly detection."""
    anomalies: List[Anomaly] = Field(default_factory=list)


class PerformanceScoreResponse(BaseModel):
    """Response for performance score."""
    score: float = Field(..., ge=0, le=100, description="Performance score 0-100")


class VisualizationDataResponse(BaseModel):
    """Response for visualization data."""
    labels: List[str] = Field(default_factory=list, description="Data labels")
    values: List[float] = Field(default_factory=list, description="Data values")
    grid: Optional[List[List[int]]] = Field(None, description="Optional grid data")


class WorkloadPatternResponse(BaseModel):
    """Response for workload pattern analysis."""
    pattern: str = Field(..., description="Pattern: 'idle', 'steady', 'bursty', 'heavy'")
    evaluated_window_seconds: int = Field(..., description="Analysis window in seconds")
    samples: int = Field(..., description="Number of samples analyzed")


class ResourceEfficiencyResponse(BaseModel):
    """Response for resource efficiency calculation."""
    space_efficiency: float = Field(..., description="Space efficiency percentage")
    cache_efficiency: float = Field(..., description="Cache efficiency percentage")
    time_efficiency: float = Field(..., description="Time efficiency percentage")


class StressTestResponse(BaseModel):
    """Response for stress test."""
    duration_seconds: float = Field(..., description="Test duration")
    intensity: str = Field(..., description="Test intensity")
    total_operations_attempted: int = Field(..., description="Operations attempted")
    errors_encountered: int = Field(..., description="Errors encountered")
    iops_achieved: float = Field(..., description="IOPS achieved")
