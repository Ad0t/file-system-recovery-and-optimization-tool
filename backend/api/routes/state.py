"""
state.py - Full file system state snapshot endpoint.

Returns the complete file system state in a format that
maps directly to the frontend's React component props.
"""

import logging
import math
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, status

from api.state import get_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/state", tags=["State"])


def _build_disk_blocks(state) -> List[Dict[str, Any]]:
    """
    Build the disk blocks array matching the frontend DiskBlock type:
    { id, state, fileId, fragment, nextBlock }
    """
    disk = state.disk
    fat = state.fat
    fsm = state.fsm

    blocks = []
    for i in range(disk.total_blocks):
        # Determine block state
        is_allocated = fsm.is_allocated(i) if hasattr(fsm, 'is_allocated') else not fsm.is_block_free(i)

        # Check if block has data
        block_data = disk.read_block(i)
        is_corrupted = False
        if hasattr(disk, 'corrupted_blocks'):
            is_corrupted = i in disk.corrupted_blocks

        # Determine state string
        if is_corrupted:
            block_state = "corrupted"
        elif i < 4:
            block_state = "reserved"
        elif is_allocated:
            block_state = "used"
        else:
            block_state = "free"

        # Find which file owns this block
        file_id = None
        fragment = 0
        next_block = None

        alloc_strategy = None

        if hasattr(fat, 'block_to_file') and i in fat.block_to_file:
            inode_num = fat.block_to_file[i]
            file_id = f"inode_{inode_num}"
            alloc_strategy = (
                fat.get_file_allocation_method(inode_num)
                if hasattr(fat, "get_file_allocation_method")
                else fat.allocation_method
            )

            # Get fragment index
            if inode_num in fat.file_to_blocks:
                file_blocks = fat.file_to_blocks[inode_num]
                if i in file_blocks:
                    fragment = file_blocks.index(i)
                    # Linked allocation: set next_block pointer
                    if alloc_strategy == "linked" and fragment < len(file_blocks) - 1:
                        next_block = file_blocks[fragment + 1]

        blocks.append({
            "id": i,
            "state": block_state,
            "fileId": file_id,
            "fragment": fragment,
            "nextBlock": next_block,
            "allocStrategy": alloc_strategy,
        })

    return blocks


def _build_files_and_dirs(state) -> tuple:
    """
    Walk the directory tree and build files + directories maps
    matching the frontend types FileEntry and DirectoryEntry.
    """
    files = {}
    directories = {}
    dir_tree = state.directory_tree
    fat = state.fat

    # Build the root directory
    root_node = dir_tree.root if hasattr(dir_tree, 'root') else None
    if root_node is None:
        # Fallback: create minimal root
        directories["root"] = {
            "id": "root",
            "name": "/",
            "parentId": None,
            "children": [],
            "path": "/",
        }
        return files, directories

    def walk_node(node, parent_id, parent_path):
        node_name = node.name if hasattr(node, 'name') else "/"
        node_path = parent_path.rstrip("/") + "/" + node_name if parent_path != "/" else "/" + node_name
        if parent_id is None:
            node_path = "/"
            node_name = "/"

        is_dir = node.is_directory if hasattr(node, 'is_directory') else True

        if is_dir:
            dir_id = "root" if parent_id is None else f"dir_{id(node)}"
            children_ids = []

            # Process children
            if hasattr(node, 'children') and isinstance(node.children, dict):
                for child_name, child_node in node.children.items():
                    child_is_dir = child_node.is_directory if hasattr(child_node, 'is_directory') else True
                    if child_is_dir:
                        child_id = f"dir_{id(child_node)}"
                    else:
                        inode_num = child_node.inode.inode_number if (hasattr(child_node, 'inode') and child_node.inode) else 0
                        child_id = f"inode_{inode_num}"

                    children_ids.append(child_id)
                    walk_node(child_node, dir_id, node_path)

            directories[dir_id] = {
                "id": dir_id,
                "name": node_name,
                "parentId": parent_id,
                "children": children_ids,
                "path": node_path,
            }
        else:
            # It's a file
            inode = node.inode if hasattr(node, 'inode') else None
            if inode:
                inode_num = inode.inode_number
                file_id = f"inode_{inode_num}"
                blocks = fat.get_file_blocks(inode_num) if hasattr(fat, 'get_file_blocks') else []
                size = inode.size_bytes if hasattr(inode, 'size_bytes') else 0

                # Calculate fragmentation
                frag = 0.0
                if len(blocks) > 1:
                    gaps = sum(1 for i in range(1, len(blocks)) if blocks[i] != blocks[i - 1] + 1)
                    frag = gaps / (len(blocks) - 1)

                # Determine allocation strategy
                alloc_strategy = (
                    fat.get_file_allocation_method(inode_num)
                    if hasattr(fat, "get_file_allocation_method")
                    else (fat.allocation_method if hasattr(fat, 'allocation_method') else "contiguous")
                )

                # Compute block count as "size" for frontend
                num_blocks = len(blocks) if blocks else (math.ceil(size / state.disk.block_size) if size > 0 else 0)

                files[file_id] = {
                    "id": file_id,
                    "name": node_name,
                    "size": num_blocks,
                    "blocks": blocks,
                    "parentDir": parent_id or "root",
                    "isDirectory": False,
                    "createdAt": int(inode.created_time.timestamp() * 1000) if hasattr(inode, 'created_time') and inode.created_time else 0,
                    "accessTime": int(inode.accessed_time.timestamp() * 1000) if hasattr(inode, 'accessed_time') and inode.accessed_time else 0,
                    "fragmentation": frag,
                    "allocationStrategy": alloc_strategy,
                    "indexBlock": None,
                }

    walk_node(root_node, None, "/")
    return files, directories


def _build_journal(state) -> List[Dict[str, Any]]:
    """
    Convert journal entries to the frontend JournalEntry format.
    """
    entries = []
    journal = state.journal

    if not hasattr(journal, 'entries'):
        return entries

    def _format_journal_details(op: str, metadata: Dict[str, Any]) -> str:
        if op == "crash":
            ctype = metadata.get("crash_type", "crash")
            sev = metadata.get("severity_pct")
            if sev is not None:
                return f"{ctype} ({float(sev):.1f}% severity)"
            return str(ctype)
        if op == "recover":
            recovered = metadata.get("recovered_blocks")
            if recovered is not None:
                return f"recovered {recovered} block(s)"
            return "recovery completed"
        if op == "fsck":
            issues = metadata.get("total_issues")
            if issues is not None:
                return f"{issues} issue(s) checked"
            return "consistency check"
        if op == "create":
            return "created"
        if op == "delete":
            return "deleted"
        if op == "cache":
            return "cache operation"
        return op

    for i, entry in enumerate(reversed(journal.entries[-50:])):
        operation = "write"
        op_str = entry.operation.lower() if hasattr(entry, 'operation') else ""
        if "create" in op_str or "mkdir" in op_str:
            operation = "create"
        elif "delete" in op_str or "rm" in op_str:
            operation = "delete"
        elif "crash" in op_str:
            operation = "crash"
        elif "recover" in op_str:
            operation = "recover"
        elif "fsck" in op_str or "check" in op_str:
            operation = "fsck"
        elif "cache" in op_str:
            operation = "cache"

        committed = entry.status == "COMMITTED" if hasattr(entry, 'status') else True
        metadata = entry.metadata if hasattr(entry, 'metadata') else {}
        file_name = metadata.get("path", "") if isinstance(metadata, dict) else str(metadata)
        details = _format_journal_details(operation, metadata if isinstance(metadata, dict) else {})

        entries.append({
            "id": i + 1,
            "timestamp": int(entry.timestamp.timestamp() * 1000) if hasattr(entry, 'timestamp') and entry.timestamp else 0,
            "operation": operation,
            "fileId": str(metadata.get("inode", "")) if isinstance(metadata, dict) else "",
            "fileName": file_name,
            "details": details,
            "committed": committed,
        })

    return entries


def _build_stats(state, disk_blocks: List[Dict]) -> Dict[str, Any]:
    """
    Compute DiskStats from the state.
    """
    total = state.disk.total_blocks
    used = sum(1 for b in disk_blocks if b["state"] == "used")
    free = sum(1 for b in disk_blocks if b["state"] == "free")
    corrupted = sum(1 for b in disk_blocks if b["state"] == "corrupted")

    # Calculate average fragmentation from files
    frag_stats = state.fat.get_fragmentation_stats() if hasattr(state.fat, 'get_fragmentation_stats') else {}
    fragmentation = frag_stats.get("fragmentation_percentage", 0) / 100.0 if frag_stats else 0

    base_speed = 5
    read_speed = round(base_speed * (1 + fragmentation * 3), 1)
    write_speed = round(base_speed * 1.5 * (1 + fragmentation * 2), 1)

    return {
        "totalBlocks": total,
        "usedBlocks": used,
        "freeBlocks": free,
        "corruptedBlocks": corrupted,
        "fragmentation": fragmentation,
        "readSpeed": read_speed,
        "writeSpeed": write_speed,
    }


def _build_cache_stats(state) -> Dict[str, Any]:
    """
    Build cache stats matching frontend CacheStats type.
    """
    try:
        raw = state.cache_manager.get_cache_stats()
        hits = raw.get("cache_hits", raw.get("hits", 0))
        misses = raw.get("cache_misses", raw.get("misses", 0))
        max_size = raw.get("max_cache_size", raw.get("maxSize", 64))
        current_size = raw.get("cache_size", raw.get("current_entries", 0))
        return {
            "hits": hits,
            "misses": misses,
            "hitRate": raw.get("hit_rate", 0),
            "entries": [],
            "maxSize": max_size,
            "currentSize": current_size,
            "evictions": raw.get("eviction_count", 0),
            "strategy": raw.get("strategy", "LRU"),
            "mostAccessedBlocks": raw.get("most_accessed_blocks", []),
            "cachedBlocks": raw.get("cached_blocks", []),
            "accessFrequency": raw.get("access_frequency", {}),
        }
    except Exception:
        return {
            "hits": 0,
            "misses": 0,
            "hitRate": 0,
            "entries": [],
            "maxSize": 64,
            "currentSize": 0,
            "evictions": 0,
            "strategy": "LRU",
            "mostAccessedBlocks": [],
            "cachedBlocks": [],
            "accessFrequency": {},
        }


@router.get("/snapshot")
async def get_full_state():
    """
    Return the full file system state in a format matching
    the frontend's React component prop types.

    This is the single source of truth for the UI.
    """
    state = get_state()
    try:
        # Build all data
        disk_blocks = _build_disk_blocks(state)
        files, directories = _build_files_and_dirs(state)
        journal = _build_journal(state)
        stats = _build_stats(state, disk_blocks)
        cache_stats = _build_cache_stats(state)

        return {
            "disk": disk_blocks,
            "files": files,
            "directories": directories,
            "journal": journal,
            "stats": stats,
            "cacheStats": cache_stats,
            "benchmarkHistory": {
                "results": [],
                "avgReadTime": 0,
                "avgWriteTime": 0,
                "totalOps": 0,
            },
            "lastFsckResult": None,
            "lastAction": "System ready",
        }
    except Exception as e:
        logger.error(f"Failed to build state snapshot: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build state snapshot: {str(e)}"
        )
