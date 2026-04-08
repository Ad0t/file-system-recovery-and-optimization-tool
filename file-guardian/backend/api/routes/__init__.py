"""
API routes package.
"""

from .files import router as files_router
from .disk import router as disk_router
from .recovery import router as recovery_router
from .optimization import router as optimization_router
from .metrics import router as metrics_router
from .state import router as state_router

__all__ = [
    "files_router",
    "disk_router",
    "recovery_router",
    "optimization_router",
    "metrics_router",
    "state_router",
]
