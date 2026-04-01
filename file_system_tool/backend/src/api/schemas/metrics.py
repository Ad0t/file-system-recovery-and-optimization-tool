from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime


class PerformanceMetrics(BaseModel):
    timestamp: datetime
    disk_usage_percentage: float
    fragmentation_percentage: float
    cache_hit_rate: float
    read_throughput_mbps: float
    write_throughput_mbps: float
    iops: int
    free_space_mb: float


class BenchmarkRequest(BaseModel):
    test_types: List[str] = ["read", "write", "defrag"]


class BenchmarkResult(BaseModel):
    test_type: str
    throughput_mbps: float
    latency_ms: float
    iops: int
