"""
optimization.py - Defragmentation and optimization API routes.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from api.state import get_state
from api.schemas.metrics import (
    FileFragmentation,
    FragmentationAnalysisResponse,
    DefragFileRequest,
    DefragFileResponse,
    DefragAllRequest,
    DefragAllResponse,
    CompactResponse,
    OptimizationStrategyRequest,
    OptimizationResponse,
    DefragPlanRequest,
    DefragPlanResponse,
    DefragSimulationResponse,
    ScheduleDefragRequest,
    ScheduleDefragResponse,
    DefragRollbackRequest,
    DefragRollbackResponse,
    DiskLayoutVisualizationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optimization", tags=["Optimization"])


# =============================================================================
# Fragmentation Analysis
# =============================================================================

@router.get("/fragmentation/analysis", response_model=FragmentationAnalysisResponse)
async def analyze_fragmentation():
    """
    Analyze current fragmentation state of the file system.

    Returns:
        FragmentationAnalysisResponse: Fragmentation statistics.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.analyze_fragmentation()

        # Convert file scores to proper model
        most_fragmented = [
            FileFragmentation(**file_data)
            for file_data in result.get("most_fragmented_files", [])
        ]

        return FragmentationAnalysisResponse(
            total_files=result["total_files"],
            fragmented_files=result["fragmented_files"],
            fragmentation_percentage=result["fragmentation_percentage"],
            most_fragmented_files=most_fragmented,
            average_fragments_per_file=result["average_fragments_per_file"],
            total_gaps=result["total_gaps"]
        )
    except Exception as e:
        logger.error(f"Failed to analyze fragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/fragmentation/file/{inode_number}", response_model=FileFragmentation)
async def get_file_fragmentation(inode_number: int):
    """
    Calculate fragmentation for a specific file.

    Args:
        inode_number: Inode number to analyze.

    Returns:
        FileFragmentation: Fragmentation details for the file.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.calculate_file_fragmentation(inode_number)
        return FileFragmentation(**result)
    except Exception as e:
        logger.error(f"Failed to get file fragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Defragmentation Operations
# =============================================================================

@router.post("/defrag/file", response_model=DefragFileResponse)
async def defragment_file(request: DefragFileRequest):
    """
    Defragment a single file.

    Args:
        request: Defrag file request with inode number.

    Returns:
        DefragFileResponse: Defragmentation result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.defragment_file(request.inode_number)
        return DefragFileResponse(**result)
    except Exception as e:
        logger.error(f"Failed to defragment file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/all", response_model=DefragAllResponse)
async def defragment_all(request: DefragAllRequest):
    """
    Defragment the entire file system.

    For 'sequential' strategy, uses compact_free_space() to move all files
    to the beginning of the disk, eliminating gaps between files.
    For other strategies, uses the standard defragment_all().

    Args:
        request: Defrag all request with strategy.

    Returns:
        DefragAllResponse: Defragmentation results.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())

        # For sequential strategy, use compaction which moves all files together
        if request.strategy == 'sequential':
            result = state.defragmenter.compact_free_space()
            # Convert compact result to DefragAllResponse format
            state.refresh_recovery_components()
            return DefragAllResponse(
                files_processed=result.get('files_moved', 0),
                total_blocks_moved=result.get('blocks_moved', 0),
                time_taken=result.get('time_taken', 0),
                initial_fragmentation_percentage=0.0,
                final_fragmentation_percentage=0.0,
                strategy_used='sequential'
            )
        else:
            result = state.defragmenter.defragment_all(strategy=request.strategy)
            state.refresh_recovery_components()
            return DefragAllResponse(**result)
    except Exception as e:
        logger.error(f"Failed to defragment all: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/compact", response_model=CompactResponse)
async def compact_free_space():
    """
    Consolidate free space into contiguous regions.

    Returns:
        CompactResponse: Compaction result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.compact_free_space()
        state.refresh_recovery_components()
        return CompactResponse(**result)
    except Exception as e:
        logger.error(f"Failed to compact free space: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/plan", response_model=DefragPlanResponse)
async def get_defragmentation_plan(request: DefragPlanRequest):
    """
    Create a detailed defragmentation plan.

    Args:
        request: Plan request with list of inodes.

    Returns:
        DefragPlanResponse: Detailed defragmentation plan.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.get_defragmentation_plan(request.inode_numbers)
        return DefragPlanResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get defrag plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/simulate")
async def simulate_defragmentation(inode_number: Optional[int] = None):
    """
    Simulate defragmentation without actually moving data.

    Args:
        inode_number: Optional specific inode to simulate, or simulate all if None.

    Returns:
        DefragSimulationResponse: Simulation results.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.simulate_defragmentation(inode_number)
        return DefragSimulationResponse(**result)
    except Exception as e:
        logger.error(f"Failed to simulate defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/schedule", response_model=ScheduleDefragResponse)
async def schedule_defragmentation(request: ScheduleDefragRequest):
    """
    Determine which files should be defragmented based on threshold.

    Args:
        request: Schedule request with fragmentation threshold.

    Returns:
        ScheduleDefragResponse: List of inodes needing defragmentation.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        targets = state.defragmenter.schedule_defragmentation(request.threshold)
        return ScheduleDefragResponse(targets=targets)
    except Exception as e:
        logger.error(f"Failed to schedule defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/rollback", response_model=DefragRollbackResponse)
async def rollback_defragmentation(request: DefragRollbackRequest):
    """
    Rollback a defragmentation operation.

    Args:
        request: Rollback request with operation ID.

    Returns:
        DefragRollbackResponse: Rollback result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        success = state.defragmenter.rollback_defragmentation(request.operation_id)
        state.refresh_recovery_components()
        return DefragRollbackResponse(success=success)
    except Exception as e:
        logger.error(f"Failed to rollback defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/defrag/visualize", response_model=DiskLayoutVisualizationResponse)
async def visualize_disk_layout(output_format: str = "text"):
    """
    Create visualization of disk block layout.

    Args:
        output_format: Output format ('text', 'ascii_art', 'data').

    Returns:
        DiskLayoutVisualizationResponse: Disk layout visualization.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        layout = state.defragmenter.visualize_disk_layout(output_format)
        return DiskLayoutVisualizationResponse(layout=layout)
    except Exception as e:
        logger.error(f"Failed to visualize disk layout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# File Placement Optimization
# =============================================================================

@router.post("/optimize/placement", response_model=OptimizationResponse)
async def optimize_file_placement(request: OptimizationStrategyRequest):
    """
    Optimize file placement based on access patterns.

    Args:
        request: Optimization request with optional access patterns.

    Returns:
        OptimizationResponse: Optimization result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.optimize_file_placement(request.access_patterns)
        state.refresh_recovery_components()
        return OptimizationResponse(**result)
    except Exception as e:
        logger.error(f"Failed to optimize file placement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/optimize/sequential")
async def optimize_for_sequential_access(file_list: List[int]):
    """
    Optimize file layout for sequential reading.

    Args:
        file_list: List of inode numbers to optimize.

    Returns:
        Optimization result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.optimize_for_sequential_access(file_list)
        state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to optimize for sequential access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/optimize/random")
async def optimize_for_random_access(file_list: List[int]):
    """
    Optimize file layout for random access.

    Args:
        file_list: List of inode numbers to optimize.

    Returns:
        Optimization result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.optimize_for_random_access(file_list)
        state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to optimize for random access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/optimize/elevator")
async def implement_elevator_algorithm(file_list: List[int]):
    """
    Sort defragmentation order using elevator/SCAN algorithm.

    Args:
        file_list: List of inode numbers to sort.

    Returns:
        Sorted list of inode numbers.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.implement_elevator_algorithm(file_list)
        return {"sorted_order": result}
    except Exception as e:
        logger.error(f"Failed to implement elevator algorithm: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Performance Improvements
# =============================================================================

@router.get("/performance/improvement")
async def measure_performance_improvement():
    """
    Measure performance before and after defragmentation.

    Returns:
        Performance improvement metrics.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.measure_performance_improvement()
        return result
    except Exception as e:
        logger.error(f"Failed to measure performance improvement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/defrag/incremental")
async def defragment_incrementally(time_budget: float = 5.0):
    """
    Perform defragmentation in small increments within a time budget.

    Args:
        time_budget: Maximum time in seconds.

    Returns:
        Incremental defragmentation result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.defragment_incrementally(time_budget)
        state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to perform incremental defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/estimate/defrag-time")
async def estimate_defrag_time(inode_numbers: List[int]):
    """
    Estimate time required for defragmentation.

    Args:
        inode_numbers: List of inodes to estimate.

    Returns:
        Time estimates per file and total.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.estimate_defrag_time(inode_numbers)
        return result
    except Exception as e:
        logger.error(f"Failed to estimate defrag time: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/online-defrag")
async def online_defragmentation(inode_number: int):
    """
    Defragment a file while it's in use using copy-on-write.

    Args:
        inode_number: Inode to defragment.

    Returns:
        Online defragmentation result.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.implement_online_defragmentation(inode_number)
        state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to perform online defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/auto-defrag")
async def auto_defragment(
    trigger_threshold: float = 40.0,
    schedule: str = "idle"
):
    """
    Automatic defragmentation with configurable triggers.

    Args:
        trigger_threshold: Fragmentation percentage to trigger defrag.
        schedule: When to run ('idle', 'manual').

    Returns:
        Auto defragmentation status.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.auto_defragment(trigger_threshold, schedule)
        if result.get("status") == "Triggered and Executed":
            state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to auto defragment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Benchmarking
# =============================================================================

@router.post("/benchmark")
async def benchmark_defragmentation(test_files: List[int]):
    """
    Benchmark defragmentation algorithms.

    Args:
        test_files: List of inode numbers to use for benchmarking.

    Returns:
        Benchmark results.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        result = state.defragmenter.benchmark_defragmentation(test_files)
        return result
    except Exception as e:
        logger.error(f"Failed to benchmark defragmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/statistics")
async def get_defragmentation_statistics():
    """
    Get defragmentation operation statistics.

    Returns:
        Defragmentation statistics.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        return state.defragmenter.statistics
    except Exception as e:
        logger.error(f"Failed to get defragmentation statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history")
async def get_defragmentation_history():
    """
    Get defragmentation operation history.

    Returns:
        List of defragmentation operations.
    """
    state = get_state()
    try:
        try:
            from recovery.defragmenter import Defragmenter
        except ImportError:
            from recovery.defragmenter import Defragmenter
        state.defragmenter = Defragmenter(state.to_dict())
        return {"history": state.defragmenter.defrag_history}
    except Exception as e:
        logger.error(f"Failed to get defragmentation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
