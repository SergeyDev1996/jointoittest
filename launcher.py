import asyncio
import subprocess
import signal
import os
from datetime import datetime
from config import settings
from redis_manager import RedisConnectionManager

redis_manager = RedisConnectionManager()

shutdown_requested = False


async def graceful_shutdown():
    print("[launcher] graceful_shutdown() ENTERED", flush=True)
    deadline = datetime.utcnow() + settings.graceful_timeout_seconds

    while True:
        active = await redis_manager.total_active_connections()
        remaining = (deadline - datetime.utcnow()).total_seconds()

        print(f"[launcher] Loop: active={active}, remaining={remaining}", flush=True)

        if active == 0:
            print("[launcher] All clients disconnected.", flush=True)
            break

        if remaining <= 0:
            print(f"[launcher] Timeout reached, forcing shutdown. active={active}", flush=True)
            break

        await asyncio.sleep(settings.status_log_interval)

    print("[launcher] Sending SIGTERM to uvicorn process group...", flush=True)
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

    try:
        proc.wait(timeout=15)
        print("[launcher] Uvicorn exited with code", proc.returncode, flush=True)
    except subprocess.TimeoutExpired:
        print("[launcher] Uvicorn did not exit in time, SIGKILL", flush=True)
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

    await redis_manager.redis.close()
    print("[launcher] Exiting launcher NOW", flush=True)
    os._exit(0)


async def redis_startup_cleanup():
    print("[launcher] Cleaning Redis startup state", flush=True)

    r = redis_manager.redis

    # Delete known global keys
    await r.delete(
        "ws:workers",
        "ws:test_broadcast_owner",
        "ws:startup_lock",
    )

    # Delete per-worker connection sets
    keys = await r.keys("ws:worker:*:connections")
    if keys:
        await r.delete(*keys)

    print("[launcher] Redis cleanup complete", flush=True)

def signal_handler(sig, frame):
    global shutdown_requested
    print(f"[launcher] signal_handler CALLED with sig={sig}", flush=True)
    if not shutdown_requested:
        shutdown_requested = True
        loop = asyncio.get_event_loop()
        loop.create_task(graceful_shutdown())


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Start uvicorn in its own process group
proc = subprocess.Popen(
    [
        "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--workers", "4",
    ],
    preexec_fn=os.setsid,  #
)


async def monitor_uvicorn():
    while True:
        ret = proc.poll()
        if ret is not None:
            print(f"[launcher] Uvicorn exited on its own with code {ret}", flush=True)
            await redis_manager.redis.close()
            os._exit(ret)
        await asyncio.sleep(1)


asyncio.get_event_loop().run_until_complete(monitor_uvicorn())
