"""
disk.py - Disk management API routes.
"""

import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from api.state import get_state
from api.schemas.disk import (
    DiskInfo,
    BlockStatus,
    BlockReadRequest,
    BlockReadResponse,
    BlockWriteRequest,
    BlockWriteResponse,
    BatchBlockRequest,
    BatchBlockWriteRequest,
    DiskFormatResponse,
    DiskSaveRequest,
    DiskLoadRequest,
    DiskPersistResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/disk", tags=["Disk Management"])


@router.get("/info", response_model=DiskInfo)
async def get_disk_info():
    """
    Get disk information and statistics.

    Returns:
        DiskInfo: Disk configuration and usage statistics.
    """
    state = get_state()
    try:
        info = state.disk.get_disk_info()
        return DiskInfo(**info)
    except Exception as e:
        logger.error(f"Failed to get disk info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/block/{block_num}", response_model=BlockStatus)
async def get_block_status(block_num: int):
    """
    Get detailed status of a specific block.

    Args:
        block_num: Block number to query.

    Returns:
        BlockStatus: Block allocation and access information.
    """
    state = get_state()
    try:
        status_dict = state.disk.get_block_status(block_num)
        return BlockStatus(**status_dict)
    except IndexError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block number: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to get block status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/block/read", response_model=BlockReadResponse)
async def read_block(request: BlockReadRequest):
    """
    Read data from a specific block.

    Args:
        request: Block read request containing block number.

    Returns:
        BlockReadResponse: Block data encoded as base64.
    """
    state = get_state()
    try:
        data = state.disk.read_block(request.block_num)
        if data is None:
            return BlockReadResponse(
                block_num=request.block_num,
                data=None,
                is_empty=True
            )
        encoded_data = base64.b64encode(data).decode('utf-8')
        return BlockReadResponse(
            block_num=request.block_num,
            data=encoded_data,
            is_empty=False
        )
    except IndexError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block number: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to read block: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/block/write", response_model=BlockWriteResponse)
async def write_block(request: BlockWriteRequest):
    """
    Write data to a specific block.

    Args:
        request: Block write request containing block number and data.

    Returns:
        BlockWriteResponse: Write operation result.
    """
    state = get_state()
    try:
        if request.encoding == "base64":
            data = base64.b64decode(request.data)
        else:
            data = request.data.encode(request.encoding)

        success = state.disk.write_block(request.block_num, data)
        return BlockWriteResponse(
            success=success,
            block_num=request.block_num,
            bytes_written=len(data)
        )
    except (IndexError, ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid write request: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to write block: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/blocks/read")
async def read_blocks(request: BatchBlockRequest):
    """
    Read multiple blocks at once.

    Args:
        request: Batch read request containing block numbers.

    Returns:
        Dictionary mapping block numbers to their data.
    """
    state = get_state()
    try:
        results = state.disk.read_blocks(request.block_numbers)
        response = {}
        for block_num, data in zip(request.block_numbers, results):
            if data is None:
                response[block_num] = {"is_empty": True, "data": None}
            else:
                response[block_num] = {
                    "is_empty": False,
                    "data": base64.b64encode(data).decode('utf-8')
                }
        return response
    except Exception as e:
        logger.error(f"Failed to read blocks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/blocks/write")
async def write_blocks(request: BatchBlockWriteRequest):
    """
    Write data to multiple blocks.

    Args:
        request: Batch write request containing block data map.

    Returns:
        Dictionary mapping block numbers to write success status.
    """
    state = get_state()
    try:
        block_data_map = {}
        for block_num, data in request.block_data.items():
            if request.encoding == "base64":
                block_data_map[block_num] = base64.b64decode(data)
            else:
                block_data_map[block_num] = data.encode(request.encoding)

        results = state.disk.write_blocks(block_data_map)
        return results
    except Exception as e:
        logger.error(f"Failed to write blocks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/format", response_model=DiskFormatResponse)
async def format_disk():
    """
    Format the disk by clearing all blocks and resetting counters.

    WARNING: This operation cannot be undone.

    Returns:
        DiskFormatResponse: Format operation result.
    """
    state = get_state()
    try:
        state.disk.format_disk()
        state.refresh_recovery_components()
        return DiskFormatResponse(
            success=True,
            message="Disk formatted successfully. All blocks cleared."
        )
    except Exception as e:
        logger.error(f"Failed to format disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/save", response_model=DiskPersistResponse)
async def save_disk(request: DiskSaveRequest):
    """
    Save disk state to a file.

    Args:
        request: Save request containing file path.

    Returns:
        DiskPersistResponse: Save operation result.
    """
    state = get_state()
    try:
        success = state.disk.save_to_file(request.filepath)
        return DiskPersistResponse(
            success=success,
            filepath=request.filepath,
            message="Disk state saved successfully" if success else "Failed to save disk state"
        )
    except Exception as e:
        logger.error(f"Failed to save disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/load", response_model=DiskPersistResponse)
async def load_disk(request: DiskLoadRequest):
    """
    Load disk state from a file.

    Args:
        request: Load request containing file path.

    Returns:
        DiskPersistResponse: Load operation result.
    """
    state = get_state()
    try:
        loaded_disk = Disk.load_from_file(request.filepath)
        state.disk = loaded_disk
        state.refresh_recovery_components()
        return DiskPersistResponse(
            success=True,
            filepath=request.filepath,
            message="Disk state loaded successfully"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disk file not found: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to load disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/allocation/map")
async def get_allocation_map():
    """
    Get free space allocation map and statistics.

    Returns:
        Allocation map including total blocks, free/used counts, fragmentation.
    """
    state = get_state()
    try:
        return state.fsm.get_allocation_map()
    except Exception as e:
        logger.error(f"Failed to get allocation map: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/allocation/strategy")
async def set_allocation_strategy(request: dict):
    """
    Set the block allocation strategy.

    Args:
        request: Dictionary containing 'strategy' field.

    Returns:
        Operation result with new strategy.
    """
    state = get_state()
    try:
        strategy = request.get("strategy", "first_fit")
        success = state.fsm.set_allocation_strategy(strategy)
        if success:
            return {"success": True, "strategy": strategy}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy: {strategy}"
            )
    except Exception as e:
        logger.error(f"Failed to set allocation strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/free-regions")
async def get_free_regions():
    """
    Get all contiguous free space regions.

    Returns:
        List of (start_block, length) tuples representing free regions.
    """
    state = get_state()
    try:
        regions = state.fsm.get_all_free_regions()
        return {"regions": regions}
    except Exception as e:
        logger.error(f"Failed to get free regions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
