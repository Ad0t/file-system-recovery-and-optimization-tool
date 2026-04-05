import sys
import os

# Add project root to path (file_system_tool/)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, "..", "..", "..", "..", ".."))

# Add project root to path so imports like 'from src.core...' work
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter, HTTPException, Request
from typing import List
import traceback

from backend.src.core.inode import Inode

from ..schemas.filesystem import (
    CreateFileRequest, CreateDirectoryRequest, DeleteItemRequest,
    FileInfo, DirectoryListing, DiskInfo, DiskVisualization, BlockStatus, FileType
)

router = APIRouter()


@router.post("/create", response_model=FileInfo)
async def create_file(request: CreateFileRequest, app_request: Request):
    """Create a new file"""
    try:
        fs = app_request.app.state.fs

        # Allocate blocks
        num_blocks = (request.size + fs.disk.block_size - 1) // fs.disk.block_size
        blocks = fs.fsm.allocate_blocks(num_blocks, contiguous=False)

        if not blocks:
            raise HTTPException(status_code=507, detail="Insufficient space")

        # Create inode
        inode = Inode(
            inode_number=len(fs.directory_tree.inode_map) + 1,
            file_type=FileType.FILE,
            size=request.size
        )
        for block in blocks:
            inode.add_block_pointer(block)

        # Add to directory tree
        success = fs.directory_tree.create_file(request.path, inode)
        if not success:
            fs.fsm.deallocate_blocks(blocks)
            raise HTTPException(status_code=409, detail="File already exists")

        # Update FAT
        fs.fat.allocate(inode.inode_number, blocks)

        # Write actual data to disk blocks
        for block in blocks:
            fs.disk.write_block(block, b'FILE_DATA' * 50)  # Write dummy data

        # Journal transaction
        txn_id = fs.journal.begin_transaction('CREATE_FILE', {
            'path': request.path,
            'inode': inode.inode_number,
            'size': request.size
        })
        fs.journal.commit_transaction(txn_id)

        # Broadcast update via WebSocket
        await fs.broadcast({
            'type': 'file_created',
            'path': request.path,
            'size': request.size
        })

        return FileInfo(
            name=request.path.split('/')[-1],
            path=request.path,
            type=FileType.FILE,
            size=request.size,
            created=inode.created_time,
            modified=inode.modified_time,
            inode_number=inode.inode_number,
            blocks=blocks
        )
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/directory", response_model=dict)
async def create_directory(request: CreateDirectoryRequest, app_request: Request):
    """Create a new directory"""
    try:
        fs = app_request.app.state.fs
        success = fs.directory_tree.create_directory(request.path)

        if not success:
            raise HTTPException(status_code=409, detail="Directory already exists")

        await fs.broadcast({
            'type': 'directory_created',
            'path': request.path
        })

        return {"success": True, "path": request.path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_item(request: DeleteItemRequest, app_request: Request):
    """Delete file or directory"""
    try:
        fs = app_request.app.state.fs

        node = fs.directory_tree.resolve_path(request.path)
        if not node:
            raise HTTPException(status_code=404, detail="Path not found")

        # Get inode and blocks
        if node.inode:
            blocks = fs.fat.get_file_blocks(node.inode.inode_number)
            fs.fsm.deallocate_blocks(blocks)
            fs.fat.deallocate(node.inode.inode_number)

        # Delete from tree
        success = fs.directory_tree.delete(request.path, recursive=request.recursive)

        if not success:
            raise HTTPException(status_code=400, detail="Cannot delete")

        await fs.broadcast({
            'type': 'item_deleted',
            'path': request.path
        })

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=DirectoryListing)
async def list_directory(path: str = "/", app_request: Request = None):
    """List directory contents"""
    try:
        fs = app_request.app.state.fs
        items_data = fs.directory_tree.list_directory(path)

        items = [
            FileInfo(
                name=item['name'],
                path=f"{path}/{item['name']}".replace('//', '/'),
                type=FileType.DIRECTORY if item['is_directory'] else FileType.FILE,
                size=item.get('size', 0),
                modified_time=item.get('modified_time', '')
            )
            for item in items_data
        ]

        return DirectoryListing(path=path, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disk/info", response_model=DiskInfo)
async def get_disk_info(app_request: Request):
    """Get disk information"""
    fs = app_request.app.state.fs
    info = fs.disk.get_disk_info()

    # Use free space manager for accurate allocation counts
    used_blocks = fs.fsm.get_allocated_count()
    free_blocks = fs.fsm.get_free_count()

    return DiskInfo(
        total_blocks=info['total_blocks'],
        block_size=info['block_size'],
        total_capacity_mb=info['total_capacity_mb'],
        used_blocks=used_blocks,
        free_blocks=free_blocks,
        usage_percentage=(used_blocks / info['total_blocks']) * 100 if info['total_blocks'] > 0 else 0
    )


@router.get("/disk/visualization", response_model=DiskVisualization)
async def get_disk_visualization(app_request: Request):
    """Get disk block visualization data"""
    fs = app_request.app.state.fs

    block_states = []
    for block_num in range(fs.disk.total_blocks):
        is_allocated = not fs.fsm.is_block_free(block_num)
        owner = fs.fat.get_block_owner(block_num) if is_allocated else None

        # Determine color
        color = "#90EE90" if not is_allocated else "#F08080"  # green/red

        block_states.append({
            "block_number": block_num,
            "status": "allocated" if is_allocated else "free",
            "color": color,
            "owner_inode": owner
        })

    disk_info = await get_disk_info(app_request)

    return DiskVisualization(
        total_blocks=fs.disk.total_blocks,
        blocks_per_row=64,  # Can be calculated based on frontend size
        block_states=block_states,
        statistics=disk_info
    )
