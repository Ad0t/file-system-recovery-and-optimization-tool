"""
files.py - File system operations API routes.
"""

import base64
import logging
import math
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.state import get_state
from api.schemas.filesystem import (
    CreateDirectoryRequest,
    CreateFileRequest,
    DeleteRequest,
    ChangeDirectoryRequest,
    WriteFileRequest,
    DirectoryListingResponse,
    FileSystemEntry,
    CreateResponse,
    DeleteResponse,
    CurrentDirectoryResponse,
    TreeStructureResponse,
    FileReadResponse,
    FileWriteResponse,
    FileInfoResponse,
    InodeInfo,
    AllocationMethodRequest,
    FATStatusResponse,
    FragmentationStats,
)

from core.inode import Inode
from core.file_allocation_table import FileAllocationTable
from utils.constants import FileSystemConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fs", tags=["File System"])


class CreateFilePowerFailRequest(BaseModel):
    """Request model for create + simulated power failure."""
    path: str
    size: int = 0
    completion_percentage: float = Field(0.5, ge=0.0, le=1.0)


@router.get("/ls", response_model=DirectoryListingResponse)
async def list_directory(path: str = "."):
    """
    List contents of a directory.

    Args:
        path: Directory path to list (default: current directory).

    Returns:
        DirectoryListingResponse: Directory entries.
    """
    state = get_state()
    try:
        entries = state.directory_tree.list_directory(path)
        return DirectoryListingResponse(
            path=path,
            entries=[FileSystemEntry(**entry) for entry in entries],
            entry_count=len(entries)
        )
    except Exception as e:
        logger.error(f"Failed to list directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/pwd", response_model=CurrentDirectoryResponse)
async def get_current_directory():
    """
    Get the current working directory.

    Returns:
        CurrentDirectoryResponse: Current directory path.
    """
    state = get_state()
    try:
        current_path = state.directory_tree.get_current_path()
        return CurrentDirectoryResponse(current_path=current_path)
    except Exception as e:
        logger.error(f"Failed to get current directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cd")
async def change_directory(request: ChangeDirectoryRequest):
    """
    Change the current working directory.

    Args:
        request: Change directory request.

    Returns:
        CurrentDirectoryResponse: New current directory path.
    """
    state = get_state()
    try:
        success = state.directory_tree.change_directory(request.path)
        if success:
            current_path = state.directory_tree.get_current_path()
            return CurrentDirectoryResponse(current_path=current_path)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to change directory to '{request.path}'"
            )
    except Exception as e:
        logger.error(f"Failed to change directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/mkdir", response_model=CreateResponse)
async def create_directory(request: CreateDirectoryRequest):
    """
    Create a new directory.

    Args:
        request: Create directory request containing path.

    Returns:
        CreateResponse: Creation result with assigned inode number.
    """
    state = get_state()
    try:
        # Create inode for directory
        inode_num = state.get_next_inode_number()
        inode = Inode(inode_num, file_type="directory")

        # Allocate block for directory
        blocks = state.fsm.allocate_blocks(1, contiguous=True)
        if blocks:
            inode.add_block_pointer(blocks[0], "direct")
            inode.update_size(state.disk.block_size)

        # Create directory in tree
        success = state.directory_tree.create_directory(request.path, inode)

        if success:
            # Journal the operation
            tx_id = state.journal.begin_transaction("MKDIR", {"path": request.path, "inode": inode_num})
            state.journal.add_redo_data(tx_id, {"path": request.path, "inode_data": inode.to_dict()})
            state.journal.commit_transaction(tx_id)

            return CreateResponse(
                success=True,
                path=request.path,
                inode_number=inode_num,
                message=f"Directory '{request.path}' created successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create directory '{request.path}'"
            )
    except Exception as e:
        logger.error(f"Failed to create directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/create", response_model=CreateResponse)
async def create_file(request: CreateFileRequest):
    """
    Create a new file.

    Args:
        request: Create file request containing path and optional size.

    Returns:
        CreateResponse: Creation result with assigned inode number.
    """
    state = get_state()
    try:
        # Create inode for file
        inode_num = state.get_next_inode_number()
        inode = Inode(inode_num, file_type="file", size=request.size)

        # Calculate and allocate blocks based on FAT allocation method
        if request.size > 0:
            num_blocks = math.ceil(request.size / state.disk.block_size)
            # Contiguous method requires contiguous blocks; linked/indexed can use scattered
            contiguous = state.fat.allocation_method == "contiguous"
            blocks = state.fsm.allocate_blocks(num_blocks, contiguous=contiguous)

            if not blocks or len(blocks) < num_blocks:
                raise HTTPException(
                    status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                    detail=(
                        f"Insufficient contiguous/free space to allocate {num_blocks} "
                        f"block(s) for '{request.path}'"
                    )
                )

            # Add block pointers to inode
            for block in blocks[:FileSystemConfig.MAX_DIRECT_POINTERS]:
                inode.add_block_pointer(block, "direct")

            # Update FAT (handles method-specific mapping)
            state.fat.allocate(inode_num, blocks)

        # Create file in tree
        success = state.directory_tree.create_file(request.path, inode)

        if success:
            # Journal the operation
            tx_id = state.journal.begin_transaction("CREATE", {"path": request.path, "inode": inode_num})
            state.journal.add_redo_data(tx_id, {"path": request.path, "inode_data": inode.to_dict()})
            state.journal.commit_transaction(tx_id)

            return CreateResponse(
                success=True,
                path=request.path,
                inode_number=inode_num,
                message=f"File '{request.path}' created successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create file '{request.path}'"
            )
    except Exception as e:
        logger.error(f"Failed to create file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/create/power-fail")
async def create_file_with_power_fail(request: CreateFilePowerFailRequest):
    """
    Create a file, then simulate a power failure during its initial write.
    """
    state = get_state()
    try:
        create_resp = await create_file(CreateFileRequest(path=request.path, size=request.size))
        inode_num = create_resp.inode_number
        file_blocks = state.fat.get_file_blocks(inode_num)

        crash_report = state.crash_simulator.inject_incomplete_write(
            state.disk,
            file_blocks=file_blocks,
            completion_percentage=request.completion_percentage
        )

        # Surface unwritten blocks as corrupted so the UI can visualize the crash.
        unwritten = crash_report.get("blocks_unwritten", [])
        if not hasattr(state.disk, "corrupted_blocks"):
            state.disk.corrupted_blocks = set()
        state.disk.corrupted_blocks.update(unwritten)

        tx_id = state.journal.begin_transaction("CRASH", {
            "crash_type": "power-fail-write",
            "path": request.path,
            "inode": inode_num,
            "blocks_unwritten": len(unwritten),
        })
        state.journal.commit_transaction(tx_id)

        # Keep a replayable journal entry so journal-replay can finish writes.
        replay_tx = state.journal.begin_transaction("INCOMPLETE_WRITE", {
            "path": request.path,
            "inode": inode_num,
            "completion_percentage": request.completion_percentage,
            "blocks_unwritten": unwritten,
        })
        state.journal.add_redo_data(replay_tx, {
            "path": request.path,
            "inode": inode_num,
            "blocks_unwritten": unwritten,
            "fill_byte": 171,
        })

        state.refresh_recovery_components()
        return {
            "success": True,
            "inode_number": inode_num,
            "message": (
                f"Created '{request.path}' with simulated power-fail write: "
                f"{len(unwritten)} block(s) left unwritten"
            ),
            "crash_report": crash_report,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create file with simulated power failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/rm", response_model=DeleteResponse)
async def delete(request: DeleteRequest):
    """
    Delete a file or directory.

    Args:
        request: Delete request containing path and recursive flag.

    Returns:
        DeleteResponse: Deletion result.
    """
    state = get_state()
    try:
        # Find the node to get inode info before deletion
        node = state.directory_tree.resolve_path(request.path)
        inode_num = None
        if node and node.inode:
            inode_num = node.inode.inode_number

        # Delete from directory tree
        success = state.directory_tree.delete(request.path, recursive=request.recursive)

        if success:
            # Deallocate blocks if file had an inode
            if inode_num:
                freed_blocks = state.fat.deallocate(inode_num)
                if freed_blocks:
                    state.fsm.deallocate_blocks(freed_blocks)

                # Journal the operation
                tx_id = state.journal.begin_transaction("DELETE", {"path": request.path, "inode": inode_num})
                state.journal.add_undo_data(tx_id, {"path": request.path, "inode": inode_num})
                state.journal.commit_transaction(tx_id)

            return DeleteResponse(
                success=True,
                path=request.path,
                message=f"'{request.path}' deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete '{request.path}'"
            )
    except Exception as e:
        logger.error(f"Failed to delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tree", response_model=TreeStructureResponse)
async def get_tree_structure():
    """
    Get ASCII tree representation of the directory structure.

    Returns:
        TreeStructureResponse: Tree visualization.
    """
    state = get_state()
    try:
        tree = state.directory_tree.get_tree_structure()
        return TreeStructureResponse(tree=tree)
    except Exception as e:
        logger.error(f"Failed to get tree structure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stat/{path:path}", response_model=FileInfoResponse)
async def get_file_info(path: str):
    """
    Get detailed information about a file or directory.

    Args:
        path: Path to the file or directory.

    Returns:
        FileInfoResponse: File metadata including inode info and block allocation.
    """
    state = get_state()
    try:
        node = state.directory_tree.resolve_path(path)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Path '{path}' not found"
            )

        if not node.inode:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inode found for '{path}'"
            )

        inode_info = InodeInfo(**node.inode.to_dict())
        blocks = state.fat.get_file_blocks(node.inode.inode_number)

        return FileInfoResponse(
            path=path,
            inode=inode_info,
            blocks=blocks
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/write", response_model=FileWriteResponse)
async def write_file(request: WriteFileRequest):
    """
    Write data to a file.

    Args:
        request: Write request containing path and data.

    Returns:
        FileWriteResponse: Write operation result.
    """
    state = get_state()
    try:
        # Resolve the file
        node = state.directory_tree.resolve_path(request.path)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{request.path}' not found"
            )

        if node.is_directory:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{request.path}' is a directory"
            )

        # Decode data
        if request.encoding == "base64":
            data = base64.b64decode(request.data)
        else:
            data = request.data.encode(request.encoding)

        # Get or create inode
        if not node.inode:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inode found for '{request.path}'"
            )

        inode_num = node.inode.inode_number

        # Calculate blocks needed
        num_blocks = math.ceil(len(data) / state.disk.block_size)

        # Get existing blocks or allocate new ones
        existing_blocks = state.fat.get_file_blocks(inode_num)
        if len(existing_blocks) < num_blocks:
            # Need more blocks
            additional = num_blocks - len(existing_blocks)
            # Contiguous method requires contiguous blocks; linked/indexed can use scattered
            contiguous = state.fat.allocation_method == "contiguous"
            new_blocks = state.fsm.allocate_blocks(additional, contiguous=contiguous)
            if not new_blocks:
                raise HTTPException(
                    status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                    detail="Insufficient free space"
                )
            all_blocks = existing_blocks + new_blocks
            state.fat.allocate(inode_num, all_blocks)
        else:
            all_blocks = existing_blocks[:num_blocks]

        # Write data to blocks
        block_size = state.disk.block_size
        for i, block_num in enumerate(all_blocks):
            start = i * block_size
            end = min(start + block_size, len(data))
            block_data = data[start:end]
            state.disk.write_block(block_num, block_data)

        # Update inode
        node.inode.update_size(len(data))
        node.inode.update_modified_time()

        # Journal the operation
        tx_id = state.journal.begin_transaction("WRITE", {"path": request.path, "inode": inode_num})
        state.journal.add_redo_data(tx_id, {"path": request.path, "size": len(data)})
        state.journal.commit_transaction(tx_id)

        return FileWriteResponse(
            success=True,
            path=request.path,
            bytes_written=len(data),
            blocks_allocated=all_blocks,
            message=f"Wrote {len(data)} bytes to '{request.path}'"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/read/{path:path}", response_model=FileReadResponse)
async def read_file(path: str):
    """
    Read data from a file.

    Args:
        path: Path to the file.

    Returns:
        FileReadResponse: File data encoded as base64.
    """
    state = get_state()
    try:
        # Resolve the file
        node = state.directory_tree.resolve_path(path)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{path}' not found"
            )

        if node.is_directory:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{path}' is a directory"
            )

        if not node.inode:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No inode found for '{path}'"
            )

        inode_num = node.inode.inode_number
        size = node.inode.size_bytes

        # Get blocks
        blocks = state.fat.get_file_blocks(inode_num)

        # Read data from blocks
        data = bytearray()
        for block_num in blocks:
            block_data = state.disk.read_block(block_num)
            if block_data:
                data.extend(block_data)

        # Trim to actual size
        data = bytes(data[:size])

        # Update access time
        node.inode.update_access_time()

        # Encode as base64
        encoded_data = base64.b64encode(data).decode('utf-8')

        return FileReadResponse(
            path=path,
            data=encoded_data,
            size=len(data),
            encoding="base64"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/fat/status", response_model=FATStatusResponse)
async def get_fat_status():
    """
    Get File Allocation Table status.

    Returns:
        FATStatusResponse: Current FAT configuration and statistics.
    """
    state = get_state()
    try:
        method = state.fat.allocation_method
        frag_stats = state.fat.get_fragmentation_stats()

        return FATStatusResponse(
            allocation_method=method,
            total_files=len(state.fat.file_to_blocks),
            blocks_used=len(state.fat.block_to_file),
            fragmentation=FragmentationStats(**frag_stats)
        )
    except Exception as e:
        logger.error(f"Failed to get FAT status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/fat/method")
async def set_allocation_method(request: AllocationMethodRequest):
    """
    Set the file allocation method.

    Args:
        request: Allocation method request.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        # Instead of replacing the FAT and deleting all files, just update the method!
        state.fat.allocation_method = request.method
        state.refresh_recovery_components()
        return {"success": True, "method": request.method}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid allocation method: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to set allocation method: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reset")
async def reset_filesystem():
    """
    Reset the file system to initial state.

    WARNING: This destroys all data and cannot be undone.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        state.reset()
        return {"success": True, "message": "File system reset complete"}
    except Exception as e:
        logger.error(f"Failed to reset file system: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
