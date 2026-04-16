"""
system.py - System-level administrative API routes.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from api.state import get_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])


@router.post("/reset")
async def factory_reset():
    """
    Factory reset the simulator state and delete persisted artifacts.
    """
    state = get_state()
    try:
        state.factory_reset()
        return {
            "status": "success",
            "message": "File system factory reset complete.",
        }
    except Exception as exc:
        logger.error("Factory reset failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Factory reset failed: {exc}",
        )
