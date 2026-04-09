"""
recovery.py - Recovery and crash simulation API routes.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from api.state import get_state
from core.inode import Inode
from api.schemas.recovery import (
    JournalEntryResponse,
    JournalStatusResponse,
    TransactionRequest,
    TransactionResponse,
    CommitRequest,
    AbortRequest,
    CrashReport,
    PowerFailureRequest,
    BitCorruptionRequest,
    MetadataCorruptionRequest,
    JournalCorruptionRequest,
    IncompleteWriteRequest,
    CascadingFailureRequest,
    CrashScenarioRequest,
    CorruptionCheckResponse,
    RecoveryResponse,
    RecoveryAnalysisResponse,
    ConsistencyCheckResponse,
    SalvageRequest,
    SalvageResponse,
    CheckpointRequest,
    SnapshotRequest,
    RestoreSnapshotRequest,
    RAIDConfigRequest,
    RAIDStatusResponse,
    ChecksumRequest,
    ChecksumVerifyResponse,
    RedundancyRecoveryRequest,
    RedundancyRecoveryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recovery", tags=["Recovery"])


# =============================================================================
# Journal Endpoints
# =============================================================================

@router.get("/journal/status", response_model=JournalStatusResponse)
async def get_journal_status():
    """
    Get journal status and statistics.

    Returns:
        JournalStatusResponse: Journal entry counts and timestamps.
    """
    state = get_state()
    try:
        stats = state.journal.get_statistics()
        return JournalStatusResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get journal status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/journal/entries", response_model=List[JournalEntryResponse])
async def get_journal_entries(
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Get journal entries.

    Args:
        status: Filter by status ('PENDING', 'COMMITTED', 'ABORTED').
        limit: Maximum number of entries to return.

    Returns:
        List of JournalEntryResponse.
    """
    state = get_state()
    try:
        entries = []
        for entry in state.journal.entries[-limit:]:
            if status and entry.status != status:
                continue
            entries.append(JournalEntryResponse(
                transaction_id=entry.transaction_id,
                timestamp=entry.timestamp.isoformat(),
                commit_timestamp=entry.commit_timestamp.isoformat() if entry.commit_timestamp else None,
                operation=entry.operation,
                status=entry.status,
                metadata=entry.metadata
            ))
        return entries
    except Exception as e:
        logger.error(f"Failed to get journal entries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/journal/uncommitted", response_model=List[JournalEntryResponse])
async def get_uncommitted_transactions():
    """
    Get all uncommitted (pending) transactions.

    Returns:
        List of pending journal entries.
    """
    state = get_state()
    try:
        entries = state.journal.get_uncommitted_transactions()
        return [
            JournalEntryResponse(
                transaction_id=entry.transaction_id,
                timestamp=entry.timestamp.isoformat(),
                commit_timestamp=None,
                operation=entry.operation,
                status=entry.status,
                metadata=entry.metadata
            )
            for entry in entries
        ]
    except Exception as e:
        logger.error(f"Failed to get uncommitted transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/begin", response_model=TransactionResponse)
async def begin_transaction(request: TransactionRequest):
    """
    Begin a new transaction.

    Args:
        request: Transaction request with operation type and metadata.

    Returns:
        TransactionResponse: Transaction ID.
    """
    state = get_state()
    try:
        tx_id = state.journal.begin_transaction(request.operation, request.metadata)
        return TransactionResponse(
            transaction_id=tx_id,
            success=True,
            message="Transaction started"
        )
    except Exception as e:
        logger.error(f"Failed to begin transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/commit", response_model=TransactionResponse)
async def commit_transaction(request: CommitRequest):
    """
    Commit a transaction.

    Args:
        request: Commit request with transaction ID.

    Returns:
        TransactionResponse: Commit result.
    """
    state = get_state()
    try:
        success = state.journal.commit_transaction(request.transaction_id)
        return TransactionResponse(
            transaction_id=request.transaction_id,
            success=success,
            message="Transaction committed" if success else "Failed to commit transaction"
        )
    except Exception as e:
        logger.error(f"Failed to commit transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/abort", response_model=TransactionResponse)
async def abort_transaction(request: AbortRequest):
    """
    Abort a transaction.

    Args:
        request: Abort request with transaction ID.

    Returns:
        TransactionResponse: Abort result.
    """
    state = get_state()
    try:
        success = state.journal.abort_transaction(request.transaction_id)
        return TransactionResponse(
            transaction_id=request.transaction_id,
            success=success,
            message="Transaction aborted" if success else "Failed to abort transaction"
        )
    except Exception as e:
        logger.error(f"Failed to abort transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/save")
async def save_journal():
    """
    Save the journal to disk.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.journal.save_journal()
        return {"success": success, "message": "Journal saved" if success else "Failed to save journal"}
    except Exception as e:
        logger.error(f"Failed to save journal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/clear")
async def clear_journal(keep_uncommitted: bool = True):
    """
    Clear journal entries.

    Args:
        keep_uncommitted: If True, preserve pending entries.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        state.journal.clear_journal(keep_uncommitted=keep_uncommitted)
        return {"success": True, "message": "Journal cleared"}
    except Exception as e:
        logger.error(f"Failed to clear journal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/checkpoint")
async def journal_checkpoint():
    """
    Prune old committed entries from the journal.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.journal.checkpoint()
        return {"success": success, "message": "Journal checkpoint completed" if success else "Checkpoint failed"}
    except Exception as e:
        logger.error(f"Failed to checkpoint journal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/journal/replay-incomplete-writes")
async def replay_incomplete_writes():
    """
    Replay pending/recorded incomplete writes from the journal.
    """
    state = get_state()
    try:
        replayed = 0
        skipped = 0
        errors = []

        for entry in getattr(state.journal, "entries", []):
            operation = getattr(entry, "operation", "")
            status = getattr(entry, "status", "")
            if operation != "INCOMPLETE_WRITE":
                continue
            if status not in ("PENDING", "COMMITTED"):
                skipped += 1
                continue

            metadata = getattr(entry, "metadata", {}) or {}
            redo_data = getattr(entry, "redo_data", {}) or {}
            blocks_unwritten = (
                redo_data.get("blocks_unwritten")
                or metadata.get("blocks_unwritten")
                or []
            )
            if not isinstance(blocks_unwritten, list) or not blocks_unwritten:
                skipped += 1
                continue

            fill_byte = int(redo_data.get("fill_byte", 0xAB)) & 0xFF
            pattern = bytes([fill_byte]) * state.disk.block_size

            try:
                for block_num in blocks_unwritten:
                    state.disk.write_block(int(block_num), pattern)
                if hasattr(state.disk, "corrupted_blocks"):
                    state.disk.corrupted_blocks.difference_update(set(blocks_unwritten))
                entry.status = "COMPLETED"
                replayed += 1
            except Exception as write_err:
                errors.append(str(write_err))

        state.refresh_recovery_components()

        success = len(errors) == 0
        message = f"Replayed {replayed} incomplete write transaction(s)"

        # Journal the replay operation
        try:
            tx_id = state.journal.begin_transaction("REPLAY_JOURNAL", {
                "success": success,
                "replayed_entries": replayed,
                "skipped_entries": skipped,
                "error_count": len(errors),
            })
            state.journal.commit_transaction(tx_id)
        except Exception:
            logger.error("Failed to journal REPLAY_JOURNAL outcome", exc_info=True)

        return {
            "success": success,
            "replayed_entries": replayed,
            "skipped_entries": skipped,
            "errors": errors,
            "message": message,
        }
    except Exception as e:
        logger.error(f"Failed to replay incomplete writes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Crash Simulation Endpoints
# =============================================================================

@router.post("/crash/power-failure", response_model=CrashReport)
async def inject_power_failure(request: PowerFailureRequest):
    """
    Simulate sudden power loss during a write operation.

    Args:
        request: Power failure request parameters.

    Returns:
        CrashReport: Crash details and affected blocks.
    """
    state = get_state()
    if request.random_seed is not None:
        state.crash_simulator = __import__('random').Random(request.random_seed)

    try:
        report = state.crash_simulator.inject_power_failure(
            state.disk,
            affected_blocks=request.affected_blocks
        )
        # Refresh recovery components after crash
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject power failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/bit-corruption", response_model=CrashReport)
async def inject_bit_corruption(request: BitCorruptionRequest):
    """
    Inject random bit corruption into disk blocks.

    Args:
        request: Bit corruption request parameters.

    Returns:
        CrashReport: Crash details and affected blocks.
    """
    state = get_state()
    if request.random_seed is not None:
        import random
        random.seed(request.random_seed)

    try:
        report = state.crash_simulator.inject_bit_corruption(
            state.disk,
            num_blocks=request.num_blocks
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject bit corruption: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/metadata-corruption", response_model=CrashReport)
async def inject_metadata_corruption(request: MetadataCorruptionRequest):
    """
    Corrupt inode metadata.

    Args:
        request: Metadata corruption request parameters.

    Returns:
        CrashReport: Crash details and affected inodes.
    """
    state = get_state()
    if request.random_seed is not None:
        import random
        random.seed(request.random_seed)

    try:
        report = state.crash_simulator.inject_metadata_corruption(
            state.directory_tree,
            num_inodes=request.num_inodes
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject metadata corruption: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/journal-corruption", response_model=CrashReport)
async def inject_journal_corruption(request: JournalCorruptionRequest):
    """
    Corrupt journal entries.

    Args:
        request: Journal corruption request parameters.

    Returns:
        CrashReport: Crash details.
    """
    state = get_state()
    if request.random_seed is not None:
        import random
        random.seed(request.random_seed)

    try:
        report = state.crash_simulator.inject_journal_corruption(
            state.journal,
            corruption_level=request.corruption_level
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject journal corruption: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/incomplete-write", response_model=CrashReport)
async def inject_incomplete_write(request: IncompleteWriteRequest):
    """
    Simulate an interrupted write operation.

    Args:
        request: Incomplete write request parameters.

    Returns:
        CrashReport: Crash details.
    """
    state = get_state()
    try:
        report = state.crash_simulator.inject_incomplete_write(
            state.disk,
            file_blocks=request.file_blocks,
            completion_percentage=request.completion_percentage
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject incomplete write: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/cascading", response_model=CrashReport)
async def inject_cascading_failure(request: CascadingFailureRequest):
    """
    Simulate multiple cascading failures.

    Args:
        request: Cascading failure request parameters.

    Returns:
        CrashReport: Crash details.
    """
    state = get_state()
    if request.random_seed is not None:
        import random
        random.seed(request.random_seed)

    try:
        report = state.crash_simulator.inject_cascading_failure(
            state.to_dict(),
            num_cascades=request.num_cascades
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to inject cascading failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/scenario", response_model=CrashReport)
async def execute_crash_scenario(request: CrashScenarioRequest):
    """
    Execute a predefined crash scenario.

    Args:
        request: Scenario name ('mild_crash', 'moderate_crash', 'severe_crash', 'catastrophic_crash').

    Returns:
        CrashReport: Crash details.
    """
    state = get_state()
    try:
        report = state.crash_simulator.create_crash_scenario(
            request.scenario_name,
            state.to_dict()
        )
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to execute crash scenario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/random", response_model=CrashReport)
async def simulate_random_crash():
    """
    Simulate a random crash.

    Returns:
        CrashReport: Crash details.
    """
    state = get_state()
    try:
        report = state.crash_simulator.simulate_random_crash(state.to_dict())
        state.refresh_recovery_components()
        return CrashReport(**report)
    except Exception as e:
        logger.error(f"Failed to simulate random crash: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/crash/history", response_model=List[CrashReport])
async def get_crash_history():
    """
    Get all injected crashes history.

    Returns:
        List of CrashReport.
    """
    state = get_state()
    try:
        return [CrashReport(**report) for report in state.crash_simulator.get_all_crashes()]
    except Exception as e:
        logger.error(f"Failed to get crash history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/crash/clear")
async def clear_crash_history():
    """
    Clear crash history.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        state.crash_simulator.clear_history()
        return {"success": True, "message": "Crash history cleared"}
    except Exception as e:
        logger.error(f"Failed to clear crash history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Recovery Operations
# =============================================================================

@router.get("/analyze", response_model=RecoveryAnalysisResponse)
async def analyze_crash():
    """
    Analyze file system for corruption.

    Returns:
        RecoveryAnalysisResponse: Analysis results and recommendations.
    """
    state = get_state()
    try:
        analysis = state.recovery_manager.analyze_crash()
        return RecoveryAnalysisResponse(**analysis)
    except Exception as e:
        logger.error(f"Failed to analyze crash: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/recover", response_model=RecoveryResponse)
async def recover_from_journal():
    """
    Perform recovery using journal replay.

    Returns:
        RecoveryResponse: Recovery results.
    """
    state = get_state()
    try:
        # Refresh recovery components before recovery
        state.refresh_recovery_components()
        result = state.recovery_manager.recover_from_journal()

        # Journal high-level recovery outcome
        try:
            tx_id = state.journal.begin_transaction("RECOVER_JOURNAL", {
                "success": result.get("success", False),
                "recovered_transactions": len(result.get("recovered_transactions", [])),
                "rolled_back_transactions": len(result.get("rolled_back_transactions", [])),
                "recovery_time": result.get("recovery_time", 0.0),
            })
            state.journal.commit_transaction(tx_id)
        except Exception:
            logger.error("Failed to journal RECOVER_JOURNAL outcome", exc_info=True)

        return RecoveryResponse(**result)
    except Exception as e:
        logger.error(f"Failed to recover: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/verify", response_model=ConsistencyCheckResponse)
async def verify_consistency():
    """
    Check file system consistency.

    Returns:
        ConsistencyCheckResponse: Verification results.
    """
    state = get_state()
    try:
        result = state.recovery_manager.verify_consistency()
        return ConsistencyCheckResponse(**result)
    except Exception as e:
        logger.error(f"Failed to verify consistency: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/salvage", response_model=SalvageResponse)
async def salvage_files(request: SalvageRequest):
    """
    Attempt to salvage readable files from corrupted system.

    Args:
        request: Salvage request with output directory.

    Returns:
        SalvageResponse: Salvage results.
    """
    state = get_state()
    try:
        result = state.recovery_manager.salvage_files(request.output_directory)
        return SalvageResponse(**result)
    except Exception as e:
        logger.error(f"Failed to salvage files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/checkpoint", response_model=TransactionResponse)
async def create_checkpoint(request: CheckpointRequest):
    """
    Create a recovery checkpoint.

    Args:
        request: Checkpoint request with optional name.

    Returns:
        TransactionResponse: Checkpoint result.
    """
    state = get_state()
    try:
        success = state.recovery_manager.create_recovery_checkpoint(request.checkpoint_name)
        return TransactionResponse(
            transaction_id=request.checkpoint_name or "checkpoint",
            success=success,
            message="Checkpoint created" if success else "Failed to create checkpoint"
        )
    except Exception as e:
        logger.error(f"Failed to create checkpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/snapshot/create")
async def create_snapshot(request: SnapshotRequest):
    """
    Create a point-in-time snapshot of the file system.

    Args:
        request: Snapshot request with name.

    Returns:
        Snapshot creation result.
    """
    state = get_state()
    try:
        result = state.recovery_manager.create_snapshot(request.snapshot_name)
        return result
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/snapshot/restore")
async def restore_snapshot(request: RestoreSnapshotRequest):
    """
    Restore file system from a snapshot.

    Args:
        request: Restore request with snapshot name.

    Returns:
        Restore result.
    """
    state = get_state()
    try:
        result = state.recovery_manager.restore_from_snapshot(request.snapshot_name)
        if result.get("success"):
            state.refresh_recovery_components()
        return result
    except Exception as e:
        logger.error(f"Failed to restore snapshot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/statistics")
async def get_recovery_statistics():
    """
    Get recovery operation statistics.

    Returns:
        Recovery statistics.
    """
    state = get_state()
    try:
        stats = state.recovery_manager.get_recovery_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get recovery statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/corruption/check", response_model=CorruptionCheckResponse)
async def validate_corruption():
    """
    Validate if file system has any corruption.

    Returns:
        CorruptionCheckResponse: Corruption status.
    """
    state = get_state()
    try:
        result = state.crash_simulator.validate_corruption(state.to_dict())
        return CorruptionCheckResponse(**result)
    except Exception as e:
        logger.error(f"Failed to validate corruption: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# RAID and Checksum
# =============================================================================

@router.post("/raid/configure", response_model=RAIDStatusResponse)
async def configure_raid(request: RAIDConfigRequest):
    """
    Configure RAID-like recovery.

    Args:
        request: RAID configuration with level.

    Returns:
        RAIDStatusResponse: RAID status.
    """
    state = get_state()
    try:
        success = state.recovery_manager.implement_raid_recovery(request.raid_level)
        return RAIDStatusResponse(
            raid_level=request.raid_level,
            is_configured=success
        )
    except Exception as e:
        logger.error(f"Failed to configure RAID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/checksum/implement")
async def implement_checksums(request: ChecksumRequest):
    """
    Implement checksum support.

    Args:
        request: Checksum request with algorithm.

    Returns:
        Operation result.
    """
    state = get_state()
    try:
        success = state.recovery_manager.implement_checksums(request.algorithm)
        return {"success": success, "algorithm": request.algorithm}
    except Exception as e:
        logger.error(f"Failed to implement checksums: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/checksum/verify", response_model=ChecksumVerifyResponse)
async def verify_checksums(request: ChecksumRequest):
    """
    Verify data integrity using checksums.

    Args:
        request: Checksum verification request.

    Returns:
        ChecksumVerifyResponse: Verification results.
    """
    state = get_state()
    try:
        result = state.recovery_manager.verify_checksums(algorithm=request.algorithm)
        return ChecksumVerifyResponse(**result)
    except Exception as e:
        logger.error(f"Failed to verify checksums: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/redundancy/recover", response_model=RedundancyRecoveryResponse)
async def recover_with_redundancy(request: RedundancyRecoveryRequest):
    """
    Use redundancy data to recover corrupted blocks.

    Args:
        request: Redundancy recovery request.

    Returns:
        RedundancyRecoveryResponse: Recovery results.
    """
    state = get_state()
    try:
        # Convert base64 strings back to bytes
        redundancy_data = {}
        for block_num, data_b64 in request.redundancy_data.items():
            import base64
            redundancy_data[int(block_num)] = base64.b64decode(data_b64)

        result = state.recovery_manager.recover_with_redundancy(redundancy_data)
        return RedundancyRecoveryResponse(**result)
    except Exception as e:
        logger.error(f"Failed to recover with redundancy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/fsck")
async def perform_fsck(auto_repair: bool = False, quarantine_orphans: bool = False):
    """
    Perform file system consistency check (fsck).

    Args:
        auto_repair: If True, automatically repair found issues.

    Returns:
        fsck results.
    """
    state = get_state()
    try:
        result = state.recovery_manager.perform_fsck(auto_repair=auto_repair)

        quarantined_files = []
        if quarantine_orphans:
            # Ensure /lost+found exists
            state.directory_tree.create_directory("/lost+found")
            orphaned_inodes = result.get("orphaned_inodes", [])

            for idx, orphan_inode in enumerate(orphaned_inodes, start=1):
                blocks = state.fat.get_file_blocks(orphan_inode) if hasattr(state.fat, "get_file_blocks") else []
                if not blocks:
                    continue

                # Move orphaned chain ownership to a recovered file.
                state.fat.deallocate(orphan_inode)
                recovered_inode = state.get_next_inode_number()
                inode = Inode(recovered_inode, file_type="file", size=len(blocks) * state.disk.block_size)
                for b in blocks[:12]:
                    inode.add_block_pointer(b, "direct")

                recovered_name = f"recovered_file_{idx:03d}.bin"
                recovered_path = f"/lost+found/{recovered_name}"
                created = state.directory_tree.create_file(recovered_path, inode)
                if not created:
                    continue

                state.fat.allocate(recovered_inode, blocks)
                if hasattr(state.fsm, "bitmap"):
                    for b in blocks:
                        state.fsm.bitmap[b] = 1
                quarantined_files.append(recovered_path)

            # Also quarantine leaked allocated blocks that are not owned by FAT.
            leaked_blocks = sorted(result.get("blocks_marked_allocated_but_free", []))
            if leaked_blocks:
                chains = []
                current_chain = [leaked_blocks[0]]
                for b in leaked_blocks[1:]:
                    if b == current_chain[-1] + 1:
                        current_chain.append(b)
                    else:
                        chains.append(current_chain)
                        current_chain = [b]
                chains.append(current_chain)

                for chain_idx, chain in enumerate(chains, start=len(quarantined_files) + 1):
                    recovered_inode = state.get_next_inode_number()
                    inode = Inode(recovered_inode, file_type="file", size=len(chain) * state.disk.block_size)
                    for b in chain[:12]:
                        inode.add_block_pointer(b, "direct")

                    recovered_name = f"recovered_file_{chain_idx:03d}.bin"
                    recovered_path = f"/lost+found/{recovered_name}"
                    created = state.directory_tree.create_file(recovered_path, inode)
                    if not created:
                        continue

                    # Force-link these blocks to the recovered inode
                    state.fat.file_to_blocks[recovered_inode] = list(chain)
                    if hasattr(state.fat, "file_to_method"):
                        state.fat.file_to_method[recovered_inode] = state.fat.allocation_method
                    for b in chain:
                        state.fat.block_to_file[b] = recovered_inode
                        if hasattr(state.fsm, "bitmap"):
                            state.fsm.bitmap[b] = 1

                    quarantined_files.append(recovered_path)

            result["quarantined_files"] = quarantined_files
            result["quarantine_dir"] = "/lost+found"
            result["quarantine_message"] = (
                f"Quarantined {len(quarantined_files)} orphan chain(s) to /lost+found"
                if quarantined_files
                else "No orphan chains detected to quarantine"
            )

        # Compute a simple severity percentage based on issue counts vs total blocks
        try:
            total_blocks = getattr(state.disk, "total_blocks", 1024)
        except Exception:
            total_blocks = 1024

        issue_counts = [
            len(result.get("orphaned_inodes", [])),
            len(result.get("blocks_marked_free_but_allocated", [])),
            len(result.get("blocks_marked_allocated_but_free", [])),
            len(result.get("invalid_directory_entries", [])),
            len(result.get("circular_references", [])),
            len(result.get("inode_link_count_mismatches", [])),
        ]
        total_issues = sum(issue_counts)
        severity_pct = (total_issues / max(1, total_blocks)) * 100.0
        result["severity_pct"] = severity_pct

        # Journal the fsck / auto-repair / quarantine summary
        try:
            tx_id = state.journal.begin_transaction("FSCK", {
                "auto_repair": auto_repair,
                "quarantine_orphans": quarantine_orphans,
                "total_issues": total_issues,
                "severity_pct": severity_pct,
                "orphaned_inodes": len(result.get("orphaned_inodes", [])),
                "blocks_marked_free_but_allocated": len(result.get("blocks_marked_free_but_allocated", [])),
                "blocks_marked_allocated_but_free": len(result.get("blocks_marked_allocated_but_free", [])),
                "quarantined_files": len(result.get("quarantined_files", [])) if quarantine_orphans else 0,
            })
            state.journal.commit_transaction(tx_id)
        except Exception:
            logger.error("Failed to journal FSCK summary", exc_info=True)

        return result
    except Exception as e:
        logger.error(f"Failed to perform fsck: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# Simple Crash/Recover for Frontend UI
# =============================================================================

from pydantic import BaseModel, Field


class SimpleCrashRequest(BaseModel):
    """Simple crash request matching the frontend ControlPanel."""
    severity: float = Field(0.3, ge=0.0, le=1.0, description="Crash severity (0-1)")
    crash_type: str = Field(
        "physical-layer",
        description=(
            "One of: physical-layer, structural-layer, "
            "transactional-layer, scenario-based"
        ),
    )


@router.post("/crash/simple")
async def simple_crash(request: SimpleCrashRequest):
    """
    Simplified crash endpoint for the frontend UI.

    Maps the frontend's crash types and severity slider to the backend's
    crash simulator. Corrupts blocks based on severity percentage.
    """
    state = get_state()
    try:
        import random
        import math

        disk = state.disk
        fat = state.fat
        fsm = state.fsm

        # Find all allocated blocks
        allocated_blocks = []
        for i in range(disk.total_blocks):
            try:
                if not fsm.is_block_free(i) and i >= 4:
                    allocated_blocks.append(i)
            except Exception:
                pass

        if not allocated_blocks:
            severity_pct = request.severity * 100.0
            return {
                "success": True,
                "crash_type": request.crash_type,
                "corrupted_blocks": 0,
                "affected_files": 0,
                "severity_pct": severity_pct,
                "message": "No blocks to corrupt",
            }

        corrupted_blocks = []
        affected_files = set()

        if request.crash_type in ("physical-layer", "power-failure"):
            # Physical layer: power failure + sector failure + bit corruption
            # Phase 1 – random scattered block corruption (bit flips / power loss)
            num_corrupt = max(1, int(len(allocated_blocks) * request.severity * 0.55))
            targets = random.sample(allocated_blocks, min(num_corrupt, len(allocated_blocks)))
            for block_num in targets:
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(block_num, corrupt_data)
                corrupted_blocks.append(block_num)
                if hasattr(fat, 'block_to_file') and block_num in fat.block_to_file:
                    affected_files.add(fat.block_to_file[block_num])
            # Phase 2 – contiguous sector failure
            sector_size = max(2, int(request.severity * 12))
            sector_start = random.randint(4, max(4, disk.total_blocks - sector_size - 1))
            for i in range(sector_start, min(sector_start + sector_size, disk.total_blocks)):
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(i, corrupt_data)
                corrupted_blocks.append(i)
                if hasattr(fat, 'block_to_file') and i in fat.block_to_file:
                    affected_files.add(fat.block_to_file[i])

        elif request.crash_type in ("structural-layer", "kernel-panic"):
            # Structural layer: metadata + directory tree + allocation table corruption
            # Corrupts blocks AND removes FAT mappings so chains visually break
            num_corrupt = max(1, int(len(allocated_blocks) * request.severity * 0.6))
            targets = random.sample(allocated_blocks, min(num_corrupt, len(allocated_blocks)))
            for block_num in targets:
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(block_num, corrupt_data)
                corrupted_blocks.append(block_num)
                if hasattr(fat, 'block_to_file') and block_num in fat.block_to_file:
                    inode_num = fat.block_to_file[block_num]
                    affected_files.add(inode_num)
                    # Break metadata: remove the block from FAT chains
                    try:
                        fat.block_to_file.pop(block_num, None)
                        if inode_num in fat.file_to_blocks:
                            fat.file_to_blocks[inode_num] = [
                                b for b in fat.file_to_blocks[inode_num] if b != block_num
                            ]
                    except Exception:
                        pass

        elif request.crash_type in ("transactional-layer", "disk-error"):
            # Transactional layer: journal + transaction + incomplete write
            # Fewer blocks corrupted but targets journal-adjacent data
            num_corrupt = max(1, int(len(allocated_blocks) * request.severity * 0.4))
            targets = random.sample(allocated_blocks, min(num_corrupt, len(allocated_blocks)))
            for block_num in targets:
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(block_num, corrupt_data)
                corrupted_blocks.append(block_num)
                if hasattr(fat, 'block_to_file') and block_num in fat.block_to_file:
                    affected_files.add(fat.block_to_file[block_num])
            # Incomplete-write effect: free the last quarter of affected blocks
            tail_start = max(0, int(len(corrupted_blocks) * 0.75))
            for block_num in corrupted_blocks[tail_start:]:
                try:
                    fsm.deallocate_blocks([block_num])
                    fat.block_to_file.pop(block_num, None)
                except Exception:
                    pass

        elif request.crash_type == "scenario-based":
            # Cascading failure: physical shock → structural cascade → sector sweep
            # Phase 1 – physical shock (scattered)
            phase1_count = max(1, int(len(allocated_blocks) * request.severity * 0.3))
            shuffled = random.sample(allocated_blocks, min(phase1_count, len(allocated_blocks)))
            for block_num in shuffled:
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(block_num, corrupt_data)
                corrupted_blocks.append(block_num)
                if hasattr(fat, 'block_to_file') and block_num in fat.block_to_file:
                    affected_files.add(fat.block_to_file[block_num])
            # Phase 2 – structural cascade (break FAT chains)
            remaining = [b for b in allocated_blocks if b not in corrupted_blocks]
            phase2_count = max(1, int(len(remaining) * request.severity * 0.25))
            phase2_targets = random.sample(remaining, min(phase2_count, len(remaining)))
            for block_num in phase2_targets:
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(block_num, corrupt_data)
                corrupted_blocks.append(block_num)
                if hasattr(fat, 'block_to_file') and block_num in fat.block_to_file:
                    inode_num = fat.block_to_file[block_num]
                    affected_files.add(inode_num)
                    try:
                        fat.block_to_file.pop(block_num, None)
                        if inode_num in fat.file_to_blocks:
                            fat.file_to_blocks[inode_num] = [
                                b for b in fat.file_to_blocks[inode_num] if b != block_num
                            ]
                    except Exception:
                        pass
            # Phase 3 – sector sweep (contiguous region)
            region_size = max(5, int(request.severity * 30))
            region_start = random.randint(4, max(4, disk.total_blocks - region_size - 1))
            for i in range(region_start, min(region_start + region_size, disk.total_blocks)):
                corrupt_data = bytes(random.getrandbits(8) for _ in range(disk.block_size))
                disk.write_block(i, corrupt_data)
                corrupted_blocks.append(i)
                if hasattr(fat, 'block_to_file') and i in fat.block_to_file:
                    affected_files.add(fat.block_to_file[i])

        # Deduplicate and register corrupted blocks with the disk
        corrupted_blocks = list(set(corrupted_blocks))
        if hasattr(disk, 'corrupted_blocks'):
            disk.corrupted_blocks.update(corrupted_blocks)
        else:
            disk.corrupted_blocks = set(corrupted_blocks)

        # Journal the crash with severity percentage
        severity_pct = request.severity * 100.0
        tx_id = state.journal.begin_transaction("CRASH", {
            "crash_type": request.crash_type,
            "severity": request.severity,
            "severity_pct": severity_pct,
            "corrupted_blocks": len(corrupted_blocks),
        })
        state.journal.commit_transaction(tx_id)

        state.refresh_recovery_components()

        return {
            "success": True,
            "crash_type": request.crash_type,
            "corrupted_blocks": len(corrupted_blocks),
            "affected_files": len(affected_files),
            "severity_pct": severity_pct,
            "message": f"{request.crash_type}: {len(corrupted_blocks)} blocks corrupted, {len(affected_files)} files affected (severity={severity_pct:.1f}%)",
        }
    except Exception as e:
        logger.error(f"Failed to simulate crash: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/recover/simple")
async def simple_recover():
    """
    Simplified recovery endpoint for the frontend UI.

    Cleans up corrupted blocks by freeing them and removing affected files.
    """
    state = get_state()
    try:
        disk = state.disk
        fat = state.fat
        fsm = state.fsm

        recovered_blocks = 0
        affected_files = set()

        # Build corrupted block set from both explicit metadata and physical markers.
        corrupted = set(getattr(disk, 'corrupted_blocks', set()) or set())
        if hasattr(disk, "read_block"):
            for block_num in range(4, disk.total_blocks):
                try:
                    data = disk.read_block(block_num)
                    if isinstance(data, (bytes, bytearray)) and b"CORRUPTED" in data:
                        corrupted.add(block_num)
                except Exception:
                    pass

        # Identify affected files BEFORE mutating mappings.
        if hasattr(fat, "file_to_blocks"):
            for inode_num, blocks in list(fat.file_to_blocks.items()):
                if isinstance(blocks, list) and any(b in corrupted for b in blocks):
                    affected_files.add(inode_num)

        # Find and clean corrupted blocks
        for block_num in list(corrupted):
            # Clear the block
            disk.write_block(block_num, bytes(disk.block_size))
            # Free the block in FSM
            try:
                if hasattr(fsm, "bitmap"):
                    fsm.bitmap[block_num] = 0
                else:
                    fsm.deallocate_blocks([block_num])
            except Exception:
                pass
            # Defensive cleanup of single-block ownership map
            if hasattr(fat, 'block_to_file'):
                fat.block_to_file.pop(block_num, None)
            recovered_blocks += 1

        # Remove affected files from FAT
        for inode_num in affected_files:
            try:
                freed_blocks = fat.deallocate(inode_num)
                # Ensure all blocks from deleted files are released in FSM/disk,
                # not only the explicitly corrupted subset.
                if freed_blocks:
                    try:
                        if hasattr(fsm, "bitmap"):
                            for b in freed_blocks:
                                fsm.bitmap[b] = 0
                        else:
                            # Fallback for alternate FSM implementations
                            for b in freed_blocks:
                                try:
                                    fsm.deallocate_blocks([b])
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    for b in freed_blocks:
                        try:
                            disk.write_block(b, bytes(disk.block_size))
                        except Exception:
                            pass
            except Exception:
                pass

        # Remove affected files from directory tree
        for inode_num in affected_files:
            try:
                # Walk tree to find and remove affected file nodes
                _remove_inode_from_tree(state.directory_tree.root, inode_num)
            except Exception:
                pass

        # Clear corrupted blocks set
        disk.corrupted_blocks = set()

        # Journal the recovery
        tx_id = state.journal.begin_transaction("RECOVER", {
            "recovered_blocks": recovered_blocks,
            "affected_files": len(affected_files),
        })
        state.journal.commit_transaction(tx_id)

        state.refresh_recovery_components()

        return {
            "success": True,
            "recovered_blocks": recovered_blocks,
            "affected_files": len(affected_files),
            "message": f"Recovery complete: {recovered_blocks} blocks recovered, {len(affected_files)} files removed",
        }
    except Exception as e:
        logger.error(f"Failed to recover: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _remove_inode_from_tree(node, inode_num):
    """Recursively remove a file with the given inode number from the tree."""
    if not hasattr(node, 'children') or not isinstance(node.children, dict):
        return
    to_remove = []
    for name, child in node.children.items():
        if hasattr(child, 'inode') and child.inode and child.inode.inode_number == inode_num:
            to_remove.append(name)
        elif hasattr(child, 'is_directory') and child.is_directory:
            _remove_inode_from_tree(child, inode_num)
    for name in to_remove:
        del node.children[name]

