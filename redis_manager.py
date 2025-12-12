import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime, timedelta
from typing import Optional

from redis.asyncio import Redis
from fastapi import WebSocket

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websocket-notifier")

class RedisConnectionManager:
    def __init__(self):
        self.connections = set()
        self._lock = asyncio.Lock()
        self.redis: Redis = Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        self._test_broadcast_task: Optional[asyncio.Task] = None

    async def _ensure_broadcast_ownership(self, worker_id):
        while True:
            owns = await self.redis.set(
                settings.test_broadcast_owner_key,
                worker_id,
                nx=True,
                ex=settings.test_broadcast_ttl_second,
            )

            if owns and self._test_broadcast_task is None:
                logger.info(f"{worker_id} became broadcast owner")
                self._test_broadcast_task = asyncio.create_task(self._test_broadcaster())

            await asyncio.sleep(settings.test_broadcast_ttl_second // 2)

    async def start(self, worker_id):
        logger.error(f"WORKER START: {worker_id}")

        await self.redis.sadd("ws:workers", worker_id)

        asyncio.create_task(self._listen_pubsub(worker_id=worker_id))
        asyncio.create_task(self._ensure_broadcast_ownership(worker_id=worker_id))

    async def _cleanup_old_state(self):

        # Remove only connection keys
        keys = await self.redis.keys("ws:worker:*:connections")
        if keys:
            await self.redis.delete(*keys)

        # Remove old worker list
        await self.redis.delete("ws:workers")

        print("Redis cleaned before first worker startup")

    async def _test_broadcaster(self):
        while True:
            await self.broadcast("Test Notification")
            await self.redis.expire(
                settings.test_broadcast_owner_key, settings.test_broadcast_ttl_second
            )
            await asyncio.sleep(10)

    async def connect(self, ws: WebSocket, worker_id: str):
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)
        logging.error(f"conn string: ws:{worker_id}:connections")
        await self.redis.sadd(f"ws:{worker_id}:connections", id(ws))

    async def disconnect(self, ws: WebSocket, worker_id: str):
        async with self._lock:
            self.connections.discard(ws)
        await self.redis.srem(f"ws:{worker_id}:connections", id(ws))

    async def broadcast(self, message: str):
        """Publish broadcast to Redis channel."""
        await self.redis.publish(settings.broadcast_channel, message)

    async def _listen_pubsub(self, worker_id):
        """Listen to broadcasts from all workers."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(settings.broadcast_channel)

        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await self._send_local(msg["data"], worker_id=worker_id)

    async def _send_local(self, message: str, worker_id: str):
        """Send a message to locally connected WS clients."""
        async with self._lock:
            for ws in list(self.connections):
                try:
                    await ws.send_text(message)
                except Exception:
                    await self.disconnect(ws, worker_id=worker_id)

    async def total_active_connections(self):
        workers = await self.redis.smembers("ws:workers")
        total = 0
        for w in workers:
            total += await self.redis.scard(f"ws:{w}:connections")
        return total
