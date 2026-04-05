import sys
import os

# Add project root to path (file_system_tool/)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, "..", "..", "..", "..", ".."))

# Add project root to path so imports like 'from src.core...' work
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter, HTTPException, Request

from ..schemas.recovery import (
    InjectCrashRequest, CrashReport, RecoveryReport, FSCKReport
)

router = APIRouter()


@router.post("/crash/inject", response_model=CrashReport)
async def inject_crash(request: InjectCrashRequest, app_request: Request):
    """Inject a crash scenario"""
    fs = app_request.app.state.fs

    components = fs.get_components()

    # Map crash type to simulator method
    crash_methods = {
        "power_failure": fs.crash_simulator.inject_power_failure,
        "bit_corruption": fs.crash_simulator.inject_bit_corruption,
        "metadata_corruption": fs.crash_simulator.inject_metadata_corruption,
        "journal_corruption": fs.crash_simulator.inject_journal_corruption,
    }

    method = crash_methods.get(request.crash_type)
    if not method:
        raise HTTPException(status_code=400, detail="Invalid crash type")

    # Inject crash
    if request.crash_type == "power_failure":
        report = method(fs.disk, request.affected_blocks)
    elif request.crash_type == "bit_corruption":
        report = method(fs.disk, num_blocks=5)
    elif request.crash_type == "metadata_corruption":
        report = method(fs.directory_tree, num_inodes=3)
    else:
        report = method(fs.journal)

    await fs.broadcast({
        'type': 'crash_injected',
        'crash_type': request.crash_type,
        'severity': report['severity']
    })

    return CrashReport(**report)


@router.post("/recover", response_model=RecoveryReport)
async def recover_system(app_request: Request):
    """Recover file system from crash"""
    fs = app_request.app.state.fs

    result = fs.recovery_manager.recover_from_journal()

    await fs.broadcast({
        'type': 'recovery_completed',
        'success': result['success']
    })

    return RecoveryReport(**result)


@router.post("/fsck", response_model=FSCKReport)
async def run_fsck(auto_repair: bool = False, app_request: Request = None):
    """Run file system check"""
    fs = app_request.app.state.fs

    result = fs.recovery_manager.perform_fsck(auto_repair=auto_repair)

    return FSCKReport(
        is_consistent=result['is_consistent'],
        issues_found=result.get('issues', []),
        issues_fixed=result.get('fixes', []) if auto_repair else [],
        orphaned_inodes=result.get('orphaned_inodes', 0),
        allocation_mismatches=result.get('allocation_mismatches', 0)
    )
