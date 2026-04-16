"""
metrics.py - Performance metrics, caching, and monitoring API routes.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status

from api.state import get_state
from api.schemas.metrics import (
    PerformanceMetrics,
    BottleneckResponse,
    PerformanceReportResponse,
    BenchmarkResponse,
    ComparisonResponse,
    IOPSCalculationResponse,
    ThroughputResponse,
    DiskFullPrediction,
    PerformanceDegradationPrediction,
    OptimizationRecommendationsResponse,
    OptimizationRecommendation,
    AnomalyDetectionResponse,
    Anomaly,
    PerformanceScoreResponse,
    VisualizationDataResponse,
    WorkloadPatternResponse,
    ResourceEfficiencyResponse,
    StressTestResponse,
    CacheConfigRequest,
    CacheStatsResponse,
    CacheStrategyRequest,
    PrefetchRequest,
    PrefetchResponse,
    PredictivePrefetchRequest,
    PredictivePrefetchResponse,
    PatternAnalysisResponse,
    CacheFlushResponse,
    DirtyBlocksResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["Metrics & Performance"])


# =============================================================================
# Performance Metrics
# =============================================================================

@router.get("/current", response_model=PerformanceMetrics)
async def get_current_metrics():
    """
    Get current performance metrics.

    Returns:
        PerformanceMetrics: Current system metrics.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        metrics = state.performance_analyzer.collect_metrics()
        return PerformanceMetrics(**metrics)
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/bottlenecks", response_model=BottleneckResponse)
async def analyze_bottlenecks():
    """
    Identify performance bottlenecks.

    Returns:
        BottleneckResponse: List of bottlenecks and recommendations.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.analyze_bottlenecks()
        return BottleneckResponse(**result)
    except Exception as e:
        logger.error(f"Failed to analyze bottlenecks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/report", response_model=PerformanceReportResponse)
async def generate_report(output_format: str = "text"):
    """
    Generate comprehensive performance report.

    Args:
        output_format: Output format ('text', 'json', 'html').

    Returns:
        PerformanceReportResponse: Formatted report.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        report = state.performance_analyzer.generate_performance_report(output_format)
        return PerformanceReportResponse(report=report)
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/score", response_model=PerformanceScoreResponse)
async def calculate_performance_score():
    """
    Calculate overall performance score (0-100).

    Returns:
        PerformanceScoreResponse: Performance score.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        score = state.performance_analyzer.calculate_performance_score()
        return PerformanceScoreResponse(score=score)
    except Exception as e:
        logger.error(f"Failed to calculate performance score: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Benchmarking
# =============================================================================

@router.post("/benchmark/read")
async def benchmark_read(
    file_sizes: Optional[List[int]] = None,
    num_iterations: int = 100
):
    """
    Benchmark read operations.

    Args:
        file_sizes: List of file sizes to benchmark.
        num_iterations: Number of iterations per size.

    Returns:
        Benchmark results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.benchmark_read_performance(file_sizes, num_iterations)
        return result
    except Exception as e:
        logger.error(f"Failed to benchmark read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/benchmark/write")
async def benchmark_write(
    file_sizes: Optional[List[int]] = None,
    num_iterations: int = 100
):
    """
    Benchmark write operations.

    Args:
        file_sizes: List of file sizes to benchmark.
        num_iterations: Number of iterations per size.

    Returns:
        Benchmark results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.benchmark_write_performance(file_sizes, num_iterations)
        return result
    except Exception as e:
        logger.error(f"Failed to benchmark write: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/benchmark/defrag-impact")
async def benchmark_defragmentation_impact():
    """
    Measure performance before and after defragmentation.

    Returns:
        Benchmark results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.benchmark_defragmentation_impact()
        return result
    except Exception as e:
        logger.error(f"Failed to benchmark defrag impact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/benchmark/cache-impact")
async def benchmark_cache_impact():
    """
    Measure performance with different cache sizes.

    Returns:
        Benchmark results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.benchmark_cache_impact()
        return result
    except Exception as e:
        logger.error(f"Failed to benchmark cache impact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/stress-test")
async def stress_test(duration: float = 60.0, intensity: str = "medium"):
    """
    Perform stress test on file system.

    Args:
        duration: Test duration in seconds.
        intensity: Test intensity ('low', 'medium', 'high').

    Returns:
        StressTestResponse: Test results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.stress_test(duration, intensity)
        return StressTestResponse(**result)
    except Exception as e:
        logger.error(f"Failed to stress test: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/iops")
async def calculate_iops(duration: float = 10.0):
    """
    Calculate I/O operations per second.

    Args:
        duration: Measurement duration in seconds.

    Returns:
        IOPSCalculationResponse: IOPS metrics.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.calculate_iops(duration)
        return IOPSCalculationResponse(**result)
    except Exception as e:
        logger.error(f"Failed to calculate IOPS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/throughput")
async def measure_throughput(block_size: int = 4096, duration: float = 10.0):
    """
    Measure data throughput.

    Args:
        block_size: Block size in bytes.
        duration: Measurement duration in seconds.

    Returns:
        ThroughputResponse: Throughput metrics.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.measure_throughput(block_size, duration)
        return ThroughputResponse(**result)
    except Exception as e:
        logger.error(f"Failed to measure throughput: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Predictions and Analysis
# =============================================================================

@router.get("/predict/disk-full", response_model=DiskFullPrediction)
async def predict_disk_full():
    """
    Predict when disk will be full based on growth rate.

    Returns:
        DiskFullPrediction: Prediction results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.predict_disk_full()
        return DiskFullPrediction(**result)
    except Exception as e:
        logger.error(f"Failed to predict disk full: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/predict/degradation", response_model=PerformanceDegradationPrediction)
async def predict_performance_degradation():
    """
    Predict future performance based on current trends.

    Returns:
        PerformanceDegradationPrediction: Prediction results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.predict_performance_degradation()
        return PerformanceDegradationPrediction(**result)
    except Exception as e:
        logger.error(f"Failed to predict performance degradation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/recommendations", response_model=OptimizationRecommendationsResponse)
async def get_optimization_recommendations():
    """
    Analyze current state and recommend optimizations.

    Returns:
        OptimizationRecommendationsResponse: List of recommendations.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.recommend_optimizations()
        recommendations = [OptimizationRecommendation(**rec) for rec in result]
        return OptimizationRecommendationsResponse(recommendations=recommendations)
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/anomalies", response_model=AnomalyDetectionResponse)
async def detect_anomalies(sensitivity: float = 2.0):
    """
    Detect anomalous performance patterns.

    Args:
        sensitivity: Detection sensitivity.

    Returns:
        AnomalyDetectionResponse: List of detected anomalies.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.detect_anomalies(sensitivity)
        anomalies = [Anomaly(**anom) for anom in result]
        return AnomalyDetectionResponse(anomalies=anomalies)
    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/workload-pattern", response_model=WorkloadPatternResponse)
async def analyze_workload_pattern(time_window: int = 3600):
    """
    Analyze workload over time window.

    Args:
        time_window: Analysis window in seconds.

    Returns:
        WorkloadPatternResponse: Pattern analysis.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.analyze_workload_pattern(time_window)
        return WorkloadPatternResponse(**result)
    except Exception as e:
        logger.error(f"Failed to analyze workload pattern: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/resource-efficiency", response_model=ResourceEfficiencyResponse)
async def calculate_resource_efficiency():
    """
    Calculate how efficiently resources are used.

    Returns:
        ResourceEfficiencyResponse: Efficiency metrics.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.calculate_resource_efficiency()
        return ResourceEfficiencyResponse(**result)
    except Exception as e:
        logger.error(f"Failed to calculate resource efficiency: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Cache Management
# =============================================================================

@router.post("/cache/configure")
async def configure_cache(request: CacheConfigRequest):
    """
    Configure cache settings.

    Args:
        request: Cache configuration request.

    Returns:
        Configuration result.
    """
    state = get_state()
    try:
        from recovery.cache_manager import CacheManager
        state.cache_manager = CacheManager(state.disk, request.cache_size, request.strategy)
        return {
            "success": True,
            "cache_size": request.cache_size,
            "strategy": request.strategy
        }
    except Exception as e:
        logger.error(f"Failed to configure cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """
    Get comprehensive cache statistics.

    Returns:
        CacheStatsResponse: Cache statistics.
    """
    state = get_state()
    try:
        result = state.cache_manager.get_cache_stats()
        return CacheStatsResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/strategy")
async def set_cache_strategy(request: CacheStrategyRequest):
    """
    Change cache strategy.

    Args:
        request: Strategy change request.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.cache_manager.set_strategy(request.strategy)
        return {
            "success": success,
            "strategy": request.strategy if success else state.cache_manager.strategy
        }
    except Exception as e:
        logger.error(f"Failed to set cache strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/prefetch", response_model=PrefetchResponse)
async def prefetch_blocks(request: PrefetchRequest):
    """
    Prefetch multiple blocks into cache.

    Args:
        request: Prefetch request with block numbers.

    Returns:
        PrefetchResponse: Number of blocks prefetched.
    """
    state = get_state()
    try:
        count = state.cache_manager.prefetch(request.block_numbers)
        return PrefetchResponse(success_count=count)
    except Exception as e:
        logger.error(f"Failed to prefetch blocks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/predictive-prefetch", response_model=PredictivePrefetchResponse)
async def predictive_prefetch(request: PredictivePrefetchRequest):
    """
    Predict and prefetch likely next blocks.

    Args:
        request: Predictive prefetch request.

    Returns:
        PredictivePrefetchResponse: Blocks prefetched.
    """
    state = get_state()
    try:
        result = state.cache_manager.predictive_prefetch(request.block_num, request.pattern)
        return PredictivePrefetchResponse(prefetched=result)
    except Exception as e:
        logger.error(f"Failed to predictive prefetch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cache/pattern-analysis", response_model=PatternAnalysisResponse)
async def analyze_access_pattern(window_size: int = 100):
    """
    Analyze recent access patterns.

    Args:
        window_size: Analysis window size.

    Returns:
        PatternAnalysisResponse: Pattern analysis.
    """
    state = get_state()
    try:
        result = state.cache_manager.analyze_access_pattern(window_size)
        return PatternAnalysisResponse(**result)
    except Exception as e:
        logger.error(f"Failed to analyze access pattern: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/resize")
async def resize_cache(new_size: int):
    """
    Change cache size dynamically.

    Args:
        new_size: New cache size.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.cache_manager.resize_cache(new_size)
        return {"success": success, "new_size": state.cache_manager.cache_size}
    except Exception as e:
        logger.error(f"Failed to resize cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear all cached data.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        state.cache_manager.clear_cache()
        return {"success": True, "message": "Cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/flush", response_model=CacheFlushResponse)
async def flush_dirty_blocks():
    """
    Write all dirty (modified) blocks to disk.

    Returns:
        CacheFlushResponse: Number of blocks flushed.
    """
    state = get_state()
    try:
        count = state.cache_manager.flush_dirty_blocks()
        return CacheFlushResponse(flushed_count=count)
    except Exception as e:
        logger.error(f"Failed to flush dirty blocks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cache/dirty-blocks", response_model=DirtyBlocksResponse)
async def get_dirty_blocks():
    """
    Get list of dirty block numbers.

    Returns:
        DirtyBlocksResponse: List of dirty blocks.
    """
    state = get_state()
    try:
        blocks = state.cache_manager.get_dirty_blocks()
        return DirtyBlocksResponse(dirty_blocks=blocks)
    except Exception as e:
        logger.error(f"Failed to get dirty blocks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cache/hit-rate")
async def get_cache_hit_rate():
    """
    Calculate cache hit rate percentage.

    Returns:
        Hit rate percentage.
    """
    state = get_state()
    try:
        rate = state.cache_manager.get_hit_rate()
        return {"hit_rate": rate}
    except Exception as e:
        logger.error(f"Failed to get cache hit rate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Monitoring
# =============================================================================

@router.post("/monitoring/start")
async def start_monitoring(interval: float = 1.0):
    """
    Start background metrics collection.

    Args:
        interval: Collection interval in seconds.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict(), interval)
        state.performance_analyzer.start_monitoring()
        return {"success": True, "message": "Monitoring started", "interval": interval}
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/monitoring/stop")
async def stop_monitoring():
    """
    Stop background monitoring.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        state.performance_analyzer.stop_monitoring()
        return {"success": True, "message": "Monitoring stopped"}
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/monitoring/history")
async def get_metrics_history():
    """
    Get collected metrics history.

    Returns:
        List of metrics.
    """
    state = get_state()
    try:
        return {"history": state.performance_analyzer.metrics_history}
    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Visualization and Export
# =============================================================================

@router.get("/visualization/{chart_type}", response_model=VisualizationDataResponse)
async def generate_visualization_data(chart_type: str):
    """
    Generate data for visualization.

    Args:
        chart_type: Type of chart ('disk_usage_timeline', 'fragmentation_heatmap',
                   'cache_hit_rate', 'throughput_comparison').

    Returns:
        VisualizationDataResponse: Chart data.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.generate_visualization_data(chart_type)

        # Convert grid to proper format if present
        if 'grid' in result:
            return VisualizationDataResponse(
                labels=result.get('labels', []),
                values=result.get('values', []),
                grid=result['grid']
            )
        return VisualizationDataResponse(
            labels=result.get('labels', []),
            values=result.get('values', [])
        )
    except Exception as e:
        logger.error(f"Failed to generate visualization data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/export")
async def export_metrics(filepath: str, format: str = "csv"):
    """
    Export metrics history to file.

    Args:
        filepath: Destination file path.
        format: Export format ('csv', 'json').

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.performance_analyzer.export_metrics(filepath, format)
        return {"success": success, "filepath": filepath}
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/import")
async def import_metrics(filepath: str):
    """
    Import metrics from file.

    Args:
        filepath: Source file path.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.performance_analyzer.import_metrics(filepath)
        return {"success": success, "filepath": filepath}
    except Exception as e:
        logger.error(f"Failed to import metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Baseline Management
# =============================================================================

@router.post("/baseline/save")
async def save_baseline(baseline_name: str = "default"):
    """
    Save current metrics as baseline.

    Args:
        baseline_name: Name for the baseline.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        success = state.performance_analyzer.save_baseline(baseline_name)
        return {"success": success, "baseline_name": baseline_name}
    except Exception as e:
        logger.error(f"Failed to save baseline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/baseline/compare")
async def compare_to_baseline(baseline_name: str = "default"):
    """
    Compare current performance against baseline.

    Args:
        baseline_name: Baseline to compare against.

    Returns:
        Comparison results.
    """
    state = get_state()
    try:
        try:
            from recovery.performance_analyzer import PerformanceAnalyzer
        except ImportError:
            from recovery.performance_analyzer import PerformanceAnalyzer
        state.performance_analyzer = PerformanceAnalyzer(state.to_dict())
        result = state.performance_analyzer.benchmark_against_baseline(baseline_name)
        return result
    except Exception as e:
        logger.error(f"Failed to compare to baseline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
