"""
main.py - FastAPI application for File Guardian.

Entry point for the REST API server, combining all routes
for file system operations, recovery mechanisms, and performance optimization.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Import routes
from .routes import (
    files_router,
    disk_router,
    recovery_router,
    optimization_router,
    metrics_router,
    state_router,
    system_router,
)
from .state import get_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Initializes the file system state on startup.
    """
    # Startup
    logger.info("Starting up File Guardian API...")
    try:
        # Initialize the file system state
        state = get_state()
        logger.info(f"File system initialized: {state.disk.total_blocks} blocks, "
                   f"{state.disk.block_size} bytes per block")
    except Exception as e:
        logger.error(f"Failed to initialize file system: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down File Guardian API...")


# Create FastAPI application
app = FastAPI(
    title="File Guardian API",
    description="""
    REST API for the File Guardian file system simulator.

    Provides endpoints for:
    - File system operations (create, read, write, delete files and directories)
    - Disk management (block I/O, allocation, persistence)
    - Recovery operations (journal replay, crash simulation, consistency checks)
    - Optimization (defragmentation, file placement, performance tuning)
    - Metrics and monitoring (cache management, performance analysis)
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status with file system information.
    """
    try:
        state = get_state()
        return {
            "status": "healthy",
            "filesystem": {
                "total_blocks": state.disk.total_blocks,
                "block_size": state.disk.block_size,
                "allocation_method": state.fat.allocation_method,
                "total_files": len(state.fat.file_to_blocks),
                "free_blocks": state.fsm.get_free_count(),
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        API information and available endpoints.
    """
    return {
        "name": "File Guardian API",
        "version": "1.0.0",
        "description": "File system simulator and recovery tool",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "files": "/fs",
            "disk": "/disk",
            "recovery": "/recovery",
            "optimization": "/optimization",
            "metrics": "/metrics",
        }
    }


# Include all routers
app.include_router(files_router, prefix="/api/v1")
app.include_router(disk_router, prefix="/api/v1")
app.include_router(recovery_router, prefix="/api/v1")
app.include_router(optimization_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(state_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error": str(exc)}
    )


# Main entry point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
