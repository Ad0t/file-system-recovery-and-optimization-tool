"""
disk.py - Pydantic schemas for disk operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# Disk Models
# =============================================================================

class DiskInfo(BaseModel):
    """Disk information response."""
    total_blocks: int = Field(..., description="Total number of blocks")
    block_size: int = Field(..., description="Block size in bytes")
    total_capacity_mb: float = Field(..., description="Total capacity in MB")
    blocks_used: int = Field(..., description="Number of used blocks")
    blocks_free: int = Field(..., description="Number of free blocks")
    total_reads: int = Field(..., description="Total read operations")
    total_writes: int = Field(..., description="Total write operations")


class BlockStatus(BaseModel):
    """Individual block status."""
    block_num: int = Field(..., description="Block number")
    is_allocated: bool = Field(..., description="Whether block is allocated")
    size_used: int = Field(..., description="Bytes used in block")
    last_accessed: Optional[float] = Field(None, description="Last access timestamp")


class BlockReadRequest(BaseModel):
    """Request to read a block."""
    block_num: int = Field(..., ge=0, description="Block number to read")


class BlockReadResponse(BaseModel):
    """Response for block read."""
    block_num: int = Field(..., description="Block number")
    data: Optional[str] = Field(None, description="Block data (base64)")
    is_empty: bool = Field(False, description="Whether block is empty")


class BlockWriteRequest(BaseModel):
    """Request to write to a block."""
    block_num: int = Field(..., ge=0, description="Block number to write")
    data: str = Field(..., description="Data to write")
    encoding: str = Field("utf-8", description="Data encoding")


class BlockWriteResponse(BaseModel):
    """Response for block write."""
    success: bool = Field(..., description="Operation success")
    block_num: int = Field(..., description="Block number")
    bytes_written: int = Field(..., description="Bytes written")


class BatchBlockRequest(BaseModel):
    """Request to read/write multiple blocks."""
    block_numbers: List[int] = Field(..., description="List of block numbers")


class BatchBlockWriteRequest(BaseModel):
    """Request to write to multiple blocks."""
    block_data: Dict[int, str] = Field(..., description="Mapping of block_num to data")
    encoding: str = Field("utf-8", description="Data encoding")


class DiskFormatResponse(BaseModel):
    """Response for disk format."""
    success: bool = Field(..., description="Format success")
    message: str = Field(..., description="Status message")


class DiskSaveRequest(BaseModel):
    """Request to save disk state."""
    filepath: str = Field(..., description="Destination file path")


class DiskLoadRequest(BaseModel):
    """Request to load disk state."""
    filepath: str = Field(..., description="Source file path")


class DiskPersistResponse(BaseModel):
    """Response for disk persistence operations."""
    success: bool = Field(..., description="Operation success")
    filepath: str = Field(..., description="File path")
    message: str = Field(..., description="Status message")
