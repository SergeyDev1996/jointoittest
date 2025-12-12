import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config import settings
from redis_manager import RedisConnectionManager

BROADCAST_CHANNEL = "ws:broadcast"
WORKER_ID = f"worker:{os.getpid()}"  # Unique per worker process

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websocket-notifier")

app = FastAPI()
app.state.manager = RedisConnectionManager()
app.state.broadcast_task: Optional[asyncio.Task] = None


async def broadcast_loop(app: FastAPI) -> None:
    """Optional periodic broadcast loop."""
    while True:
        await asyncio.sleep(settings.broadcast_interval_seconds)
        ts = datetime.utcnow().isoformat()
        await app.state.manager.broadcast(f"Test notification at {ts}Z")


# -------------------------------------------------------------------
# LIFECYCLE EVENTS
# -------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    worker_id = f"worker:{os.getpid()}"
    logger.info("Starting worker %s", WORKER_ID)
    await app.state.manager.start(worker_id=worker_id)

    # Optional periodic broadcast; you can disable this if not needed
    # app.state.broadcast_task = asyncio.create_task(broadcast_loop(app))

    logger.info("Startup complete. WebSocket server ready.")

# ------------------------------------------------------------------
# WEBSOCKET ENDPOINT
# -------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    worker_id = f"worker:{os.getpid()}"
    await app.state.manager.connect(ws=ws, worker_id=worker_id)
    try:
        while True:
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect:
                break
            # Echo to all
            await app.state.manager.broadcast(f"Echo from {WORKER_ID}: {msg}")
    finally:
        await app.state.manager.disconnect(ws, worker_id=worker_id)


# -------------------------------------------------------------------
# SIMPLE HTTP HEALTHCHECK
# -------------------------------------------------------------------
@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "WebSocket notifier running", "worker": WORKER_ID}
