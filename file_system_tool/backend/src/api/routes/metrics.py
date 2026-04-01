import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, project_root)

from fastapi import APIRouter, Request
from typing import List

from ..schemas.metrics import (
    PerformanceMetrics, BenchmarkRequest, BenchmarkResult
)

router = APIRouter()


@router.get("/current", response_model=PerformanceMetrics)
async def get_current_metrics(app_request: Request):
    """Get current performance metrics"""
    fs = app_request.app.state.fs

    metrics = fs.performance_analyzer.collect_metrics()

    return PerformanceMetrics(**metrics)


@router.post("/benchmark", response_model=List[BenchmarkResult])
async def run_benchmark(request: BenchmarkRequest, app_request: Request):
    """Run performance benchmarks"""
    fs = app_request.app.state.fs

    results = []

    if "read" in request.test_types:
        read_result = fs.performance_analyzer.benchmark_read_performance()
        results.append(BenchmarkResult(
            test_type="read",
            throughput_mbps=read_result.get('sequential_read_mbps', {}).get(4096, 0),
            latency_ms=read_result.get('average_read_latency_ms', {}).get(4096, 0),
            iops=0
        ))

    if "write" in request.test_types:
        write_result = fs.performance_analyzer.benchmark_write_performance()
        results.append(BenchmarkResult(
            test_type="write",
            throughput_mbps=write_result.get('sequential_write_mbps', {}).get(4096, 0),
            latency_ms=write_result.get('average_write_latency_ms', {}).get(4096, 0),
            iops=0
        ))

    return results
