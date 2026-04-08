"""
recovery.py - Pydantic schemas for recovery operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Journal Models
# =============================================================================

class JournalEntryResponse(BaseModel):
    """Journal entry response."""
    transaction_id: str = Field(..., description="Unique transaction ID")
    timestamp: str = Field(..., description="Entry timestamp (ISO format)")
    commit_timestamp: Optional[str] = Field(None, description="Commit timestamp")
    operation: str = Field(..., description="Operation type (CREATE, DELETE, WRITE, etc.)")
    status: str = Field(..., description="Entry status (PENDING, COMMITTED, ABORTED)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operation metadata")


class JournalStatusResponse(BaseModel):
    """Journal status response."""
    total_entries: int = Field(..., description="Total number of entries")
    pending_count: int = Field(..., description="Number of pending entries")
    committed_count: int = Field(..., description="Number of committed entries")
    aborted_count: int = Field(..., description="Number of aborted entries")
    oldest_entry_timestamp: Optional[str] = Field(None, description="Oldest entry timestamp")
    newest_entry_timestamp: Optional[str] = Field(None, description="Newest entry timestamp")


class TransactionRequest(BaseModel):
    """Request to begin a transaction."""
    operation: str = Field(..., description="Operation type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Transaction metadata")


class TransactionResponse(BaseModel):
    """Transaction operation response."""
    transaction_id: str = Field(..., description="Transaction ID")
    success: bool = Field(..., description="Operation success")
    message: str = Field("", description="Status message")


class CommitRequest(BaseModel):
    """Request to commit a transaction."""
    transaction_id: str = Field(..., description="Transaction ID to commit")


class AbortRequest(BaseModel):
    """Request to abort a transaction."""
    transaction_id: str = Field(..., description="Transaction ID to abort")


# =============================================================================
# Crash Simulation Models
# =============================================================================

class CrashReport(BaseModel):
    """Crash report model."""
    crash_id: int = Field(..., description="Unique crash ID")
    crash_type: str = Field(..., description="Type of crash")
    timestamp: datetime = Field(..., description="Crash timestamp")
    severity: str = Field(..., description="Severity level (LOW, MEDIUM, HIGH, CRITICAL)")
    description: str = Field(..., description="Crash description")
    recoverable: bool = Field(..., description="Whether crash is recoverable")
    recovery_difficulty: str = Field(..., description="Recovery difficulty")
    affected_blocks: Optional[List[int]] = Field(None, description="Affected block numbers")
    affected_inodes: Optional[List[int]] = Field(None, description="Affected inode numbers")


class CrashInjectRequest(BaseModel):
    """Base request for crash injection."""
    random_seed: Optional[int] = Field(None, description="Random seed for reproducibility")


class PowerFailureRequest(CrashInjectRequest):
    """Request to inject power failure."""
    affected_blocks: Optional[List[int]] = Field(None, description="Specific blocks to affect")


class BitCorruptionRequest(CrashInjectRequest):
    """Request to inject bit corruption."""
    num_blocks: int = Field(5, ge=1, description="Number of blocks to corrupt")


class MetadataCorruptionRequest(CrashInjectRequest):
    """Request to inject metadata corruption."""
    num_inodes: int = Field(3, ge=1, description="Number of inodes to corrupt")


class JournalCorruptionRequest(CrashInjectRequest):
    """Request to inject journal corruption."""
    corruption_level: str = Field("partial", description="Corruption level: 'partial', 'complete', 'transaction_only'")


class IncompleteWriteRequest(CrashInjectRequest):
    """Request to simulate incomplete write."""
    file_blocks: List[int] = Field(..., description="Blocks being written")
    completion_percentage: float = Field(0.5, ge=0.0, le=1.0, description="Completion fraction")


class CascadingFailureRequest(CrashInjectRequest):
    """Request to inject cascading failure."""
    num_cascades: int = Field(3, ge=1, description="Number of cascading failures")


class CrashScenarioRequest(BaseModel):
    """Request to execute a predefined crash scenario."""
    scenario_name: str = Field(..., description="Scenario: 'mild_crash', 'moderate_crash', 'severe_crash', 'catastrophic_crash'")


class CorruptionCheckResponse(BaseModel):
    """Response for corruption check."""
    is_corrupted: bool = Field(..., description="Whether corruption was detected")
    corruption_points: List[str] = Field(default_factory=list, description="Description of corruption points")
    severity: str = Field(..., description="Overall severity")
    affected_components: List[str] = Field(default_factory=list, description="Affected component names")


# =============================================================================
# Recovery Models
# =============================================================================

class RecoveryRequest(BaseModel):
    """Request to perform recovery."""
    method: str = Field("journal_replay", description="Recovery method to use")


class RecoveryResponse(BaseModel):
    """Recovery operation response."""
    success: bool = Field(..., description="Overall success")
    recovered_transactions: List[str] = Field(default_factory=list, description="IDs of recovered transactions")
    rolled_back_transactions: List[str] = Field(default_factory=list, description="IDs of rolled back transactions")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    recovery_time: float = Field(..., description="Time taken in seconds")


class RecoveryAnalysisResponse(BaseModel):
    """Response for crash analysis."""
    has_corruption: bool = Field(..., description="Whether corruption was found")
    uncommitted_transactions: List[Dict[str, Any]] = Field(default_factory=list, description="Uncommitted transactions")
    corrupted_blocks: List[int] = Field(default_factory=list, description="Corrupted block numbers")
    inconsistent_metadata: List[str] = Field(default_factory=list, description="Inconsistency descriptions")
    recommended_recovery_method: str = Field(..., description="Recommended recovery approach")


class ConsistencyCheckResponse(BaseModel):
    """Response for consistency check."""
    is_consistent: bool = Field(..., description="Whether file system is consistent")
    issues: List[str] = Field(default_factory=list, description="List of issues found")


class SalvageRequest(BaseModel):
    """Request to salvage files."""
    output_directory: str = Field("recovered/", description="Output directory for salvaged files")


class SalvageResponse(BaseModel):
    """Response for file salvage."""
    files_salvaged: int = Field(..., description="Number of files salvaged")
    total_bytes_recovered: int = Field(..., description="Total bytes recovered")
    unsalvageable_files: List[Any] = Field(default_factory=list, description="Files that couldn't be salvaged")


class CheckpointRequest(BaseModel):
    """Request to create checkpoint."""
    checkpoint_name: Optional[str] = Field(None, description="Checkpoint name")


class SnapshotRequest(BaseModel):
    """Request to create snapshot."""
    snapshot_name: str = Field(..., description="Snapshot name")


class RestoreSnapshotRequest(BaseModel):
    """Request to restore from snapshot."""
    snapshot_name: str = Field(..., description="Snapshot name to restore")


# =============================================================================
# RAID & Redundancy Models
# =============================================================================

class RAIDConfigRequest(BaseModel):
    """Request to configure RAID."""
    raid_level: int = Field(1, description="RAID level: 1 (mirror) or 5 (parity)")


class RAIDStatusResponse(BaseModel):
    """RAID status response."""
    raid_level: int = Field(..., description="Current RAID level")
    is_configured: bool = Field(..., description="Whether RAID is configured")


class ChecksumRequest(BaseModel):
    """Request to implement checksums."""
    algorithm: str = Field("crc32", description="Algorithm: 'crc32', 'md5', or 'sha256'")


class ChecksumVerifyResponse(BaseModel):
    """Response for checksum verification."""
    total_checked: int = Field(..., description="Number of blocks checked")
    corrupted_blocks: List[int] = Field(default_factory=list, description="Corrupted block numbers")
    corruption_percentage: float = Field(..., description="Corruption percentage")


class RedundancyRecoveryRequest(BaseModel):
    """Request for redundancy-based recovery."""
    redundancy_data: Dict[int, str] = Field(..., description="Mapping of block_num to backup data")


class RedundancyRecoveryResponse(BaseModel):
    """Response for redundancy recovery."""
    recovered_blocks_count: int = Field(..., description="Number of blocks recovered")
    failed_recovery_count: int = Field(..., description="Number of failed recoveries")
    success: bool = Field(..., description="Overall success")
