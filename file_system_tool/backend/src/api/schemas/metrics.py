from pydantic import BaseModel
from typing import List, Dict


class PerformanceMetrics(BaseModel):
    timestamp: float
    disk_usage_percentage: float
    fragmentation_percentage: float
    cache_hit_rate: float
    average_read_time: float
    average_write_time: float
    total_operations: int
    free_space_percentage: float


class BenchmarkRequest(BaseModel):
    test_types: List[str] = ["read", "write", "defrag"]


class BenchmarkResult(BaseModel):
    test_type: str
    throughput_mbps: float
    latency_ms: float
    iops: int
