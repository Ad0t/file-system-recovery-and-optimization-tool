import sys
import os

# Add project root to path (file_system_tool/)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, "..", "..", "..", "..", ".."))

# Add project root to path so imports like 'from src.core...' work
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter, Request

from ..schemas.optimization import (
    DefragmentationRequest, DefragmentationReport,
    FragmentationAnalysis, CacheConfig, CacheStats
)

router = APIRouter()


@router.post("/defragment", response_model=DefragmentationReport)
async def defragment(request: DefragmentationRequest, app_request: Request):
    """Defragment file system"""
    fs = app_request.app.state.fs

    if request.inode_number:
        result = fs.defragmenter.defragment_file(request.inode_number)
    else:
        result = fs.defragmenter.defragment_all(strategy=request.strategy)

    await fs.broadcast({
        'type': 'defragmentation_completed',
        'files_processed': result.get('files_defragmented', 0)
    })

    return DefragmentationReport(**result)


@router.get("/fragmentation", response_model=FragmentationAnalysis)
async def analyze_fragmentation(app_request: Request):
    """Analyze file system fragmentation"""
    fs = app_request.app.state.fs

    analysis = fs.defragmenter.analyze_fragmentation()

    return FragmentationAnalysis(**analysis)


@router.post("/cache/config")
async def configure_cache(config: CacheConfig, app_request: Request):
    """Configure cache settings"""
    fs = app_request.app.state.fs

    fs.cache_manager.resize_cache(config.cache_size)
    fs.cache_manager.set_strategy(config.strategy)

    return {"success": True, "config": config}


@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_stats(app_request: Request):
    """Get cache statistics"""
    fs = app_request.app.state.fs

    stats = fs.cache_manager.get_cache_stats()

    return CacheStats(**stats)
