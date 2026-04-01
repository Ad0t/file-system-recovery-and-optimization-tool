from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class CrashType(str, Enum):
    POWER_FAILURE = "power_failure"
    BIT_CORRUPTION = "bit_corruption"
    METADATA_CORRUPTION = "metadata_corruption"
    JOURNAL_CORRUPTION = "journal_corruption"


class InjectCrashRequest(BaseModel):
    crash_type: CrashType
    severity: str = "medium"  # low, medium, high
    affected_blocks: Optional[List[int]] = None


class CrashReport(BaseModel):
    crash_id: int
    crash_type: str
    timestamp: datetime
    affected_blocks: List[int]
    severity: str
    recoverable: bool
    description: str


class RecoveryReport(BaseModel):
    success: bool
    recovered_transactions: int
    rolled_back_transactions: int
    recovery_time: float
    errors: List[str]


class FSCKReport(BaseModel):
    is_consistent: bool
    issues_found: List[str]
    issues_fixed: List[str]
    orphaned_inodes: int
    allocation_mismatches: int
