from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class CreateFileRequest(BaseModel):
    path: str = Field(..., description="Full path including filename")
    size: int = Field(..., ge=0, description="File size in bytes")


class CreateDirectoryRequest(BaseModel):
    path: str = Field(..., description="Full path for directory")


class DeleteItemRequest(BaseModel):
    path: str = Field(..., description="Path to delete")
    recursive: bool = Field(default=False, description="Recursive delete for directories")


class FileInfo(BaseModel):
    name: str
    path: str
    type: FileType
    size: Optional[int] = None
    created: datetime
    modified: datetime
    inode_number: Optional[int] = None
    blocks: Optional[List[int]] = None


class DirectoryListing(BaseModel):
    path: str
    items: List[FileInfo]


class DiskInfo(BaseModel):
    total_blocks: int
    block_size: int
    total_capacity_mb: float
    used_blocks: int
    free_blocks: int
    usage_percentage: float


class BlockStatus(BaseModel):
    block_number: int
    is_allocated: bool
    owner_inode: Optional[int] = None
    owner_file: Optional[str] = None


class DiskVisualization(BaseModel):
    total_blocks: int
    blocks_per_row: int
    block_states: List[Dict[str, Any]]  # {block_num, status, color, owner}
    statistics: DiskInfo
