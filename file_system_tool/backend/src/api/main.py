import sys
import os

# Add project root to path so we can import from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, project_root)

from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import json
from typing import Dict, Any

# Import file system components
from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.inode import Inode
from src.core.directory import DirectoryTree
from src.core.file_allocation_table import FileAllocationTable
from src.core.journal import Journal

from src.recovery.crash_simulator import CrashSimulator
from src.recovery.recovery_manager import RecoveryManager
from src.recovery.defragmenter import Defragmenter
from src.recovery.cache_manager import CacheManager
from src.recovery.performance_analyzer import PerformanceAnalyzer

from .state import AppState
from .routes import files, recovery, optimization, metrics
from .websocket import manager


async def broadcast_metrics():
    """Periodically broadcast metrics to all connected clients"""
    while True:
        try:
            if hasattr(app.state, 'fs') and app.state.fs.websocket_connections:
                metrics = app.state.fs.performance_analyzer.collect_metrics()
                await app.state.fs.broadcast({
                    "type": "metrics_update",
                    "data": metrics
                })
        except Exception as e:
            print(f"Error broadcasting metrics: {e}")

        await asyncio.sleep(2)  # Broadcast every 2 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize file system
    app.state.fs = AppState()
    app.state.fs.initialize_filesystem(total_blocks=1000, block_size=4096)
    print("File system initialized")

    # Start metrics broadcasting
    metrics_task = asyncio.create_task(broadcast_metrics())

    yield

    # Cancel background task
    metrics_task.cancel()

    # Shutdown: Cleanup
    print("Shutting down...")

app = FastAPI(
    title="File System Recovery API",
    description="REST API for File System Recovery and Optimization Tool",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(recovery.router, prefix="/api/recovery", tags=["Recovery"])
app.include_router(optimization.router, prefix="/api/optimization", tags=["Optimization"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "File System Recovery API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "filesystem_initialized": hasattr(app.state, 'fs')
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Add to app state for broadcasting
    app.state.fs.websocket_connections.append(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to File System API"
        })

        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Echo back (can be used for ping/pong)
            await websocket.send_json({
                "type": "echo",
                "data": message
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        app.state.fs.websocket_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        if websocket in app.state.fs.websocket_connections:
            app.state.fs.websocket_connections.remove(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
