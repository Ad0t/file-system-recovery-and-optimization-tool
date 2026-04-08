"""
filesystem.py - Pydantic schemas for file system operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Base Models
# =============================================================================

class FileSystemEntry(BaseModel):
    """Base model for file system entries."""
    name: str = Field(..., description="Name of the file or directory")
    is_directory: bool = Field(..., description="True if directory, False if file")
    size: int = Field(0, description="Size in bytes")
    modified_time: Optional[str] = Field(None, description="ISO-formatted timestamp")


class InodeInfo(BaseModel):
    """Inode information model."""
    inode_number: int = Field(..., description="Unique inode identifier")
    file_type: str = Field(..., description="'file' or 'directory'")
    size_bytes: int = Field(..., description="Logical file size")
    block_count: int = Field(..., description="Number of blocks allocated")
    created_time: str = Field(..., description="ISO-formatted creation timestamp")
    modified_time: str = Field(..., description="ISO-formatted modification timestamp")
    accessed_time: str = Field(..., description="ISO-formatted access timestamp")
    permissions: str = Field(..., description="Permission string (e.g., 'rwx')")
    owner: str = Field(..., description="Owner name")
    direct_pointers: List[int] = Field(default_factory=list, description="Direct block pointers")
    single_indirect: Optional[int] = Field(None, description="Single indirect block")
    double_indirect: Optional[int] = Field(None, description="Double indirect block")
    link_count: int = Field(1, description="Number of hard links")


# =============================================================================
# Request Models
# =============================================================================

class CreateDirectoryRequest(BaseModel):
    """Request to create a directory."""
    path: str = Field(..., description="Absolute path for the new directory")


class CreateFileRequest(BaseModel):
    """Request to create a file."""
    path: str = Field(..., description="Absolute path for the new file")
    size: int = Field(0, ge=0, description="Initial file size in bytes")


class DeleteRequest(BaseModel):
    """Request to delete a file or directory."""
    path: str = Field(..., description="Path to delete")
    recursive: bool = Field(False, description="Delete non-empty directories recursively")


class ChangeDirectoryRequest(BaseModel):
    """Request to change current directory."""
    path: str = Field(..., description="Target directory path")


class WriteFileRequest(BaseModel):
    """Request to write data to a file."""
    path: str = Field(..., description="File path")
    data: str = Field(..., description="Data to write (base64 or raw string)")
    encoding: str = Field("utf-8", description="Data encoding")


class ReadFileRequest(BaseModel):
    """Request to read a file."""
    path: str = Field(..., description="File path")


# =============================================================================
# Response Models
# =============================================================================

class DirectoryListingResponse(BaseModel):
    """Response for directory listing."""
    path: str = Field(..., description="Directory path")
    entries: List[FileSystemEntry] = Field(default_factory=list, description="Directory contents")
    entry_count: int = Field(0, description="Number of entries")


class FileInfoResponse(BaseModel):
    """Response for file information."""
    path: str = Field(..., description="File path")
    inode: InodeInfo = Field(..., description="Inode metadata")
    blocks: List[int] = Field(default_factory=list, description="Allocated block numbers")


class CreateResponse(BaseModel):
    """Response for create operations."""
    success: bool = Field(..., description="Operation success status")
    path: str = Field(..., description="Created path")
    inode_number: Optional[int] = Field(None, description="Assigned inode number")
    message: str = Field("", description="Status message")


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    success: bool = Field(..., description="Operation success status")
    path: str = Field(..., description="Deleted path")
    message: str = Field("", description="Status message")


class CurrentDirectoryResponse(BaseModel):
    """Response for current directory query."""
    current_path: str = Field(..., description="Current working directory")


class TreeStructureResponse(BaseModel):
    """Response for tree structure."""
    tree: str = Field(..., description="ASCII tree representation")


class FileReadResponse(BaseModel):
    """Response for file read."""
    path: str = Field(..., description="File path")
    data: Optional[str] = Field(None, description="File data (base64 encoded)")
    size: int = Field(0, description="Data size in bytes")
    encoding: str = Field("base64", description="Data encoding")


class FileWriteResponse(BaseModel):
    """Response for file write."""
    success: bool = Field(..., description="Operation success status")
    path: str = Field(..., description="File path")
    bytes_written: int = Field(0, description="Number of bytes written")
    blocks_allocated: List[int] = Field(default_factory=list, description="Allocated block numbers")
    message: str = Field("", description="Status message")


# =============================================================================
# Allocation & FAT Models
# =============================================================================

class AllocationMethodRequest(BaseModel):
    """Request to change allocation method."""
    method: str = Field(..., description="Allocation method: 'contiguous', 'linked', or 'indexed'")


class AllocationStrategyRequest(BaseModel):
    """Request to change allocation strategy."""
    strategy: str = Field(..., description="Strategy: 'first_fit', 'best_fit', or 'worst_fit'")


class FragmentationStats(BaseModel):
    """Fragmentation statistics."""
    total_files: int = Field(..., description="Total number of files")
    fragmented_files: int = Field(..., description="Number of fragmented files")
    fragmentation_percentage: float = Field(..., description="Fragmentation percentage")
    avg_gaps_per_file: float = Field(..., description="Average gaps per file")


class FATStatusResponse(BaseModel):
    """FAT status response."""
    allocation_method: str = Field(..., description="Current allocation method")
    total_files: int = Field(..., description="Total files in FAT")
    blocks_used: int = Field(..., description="Total blocks allocated")
    fragmentation: FragmentationStats = Field(..., description="Fragmentation statistics")
