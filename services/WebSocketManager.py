# services/WebSocketManager.py
import json
import logging
import asyncio
from fastapi import WebSocket
from typing import Dict, List
import redis.asyncio as redis
import os

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps room_id to a list of active WebSockets in THIS worker
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Connect to Redis
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
        self.pubsub = self.redis_client.pubsub()
        
        # Start background listener for cross-worker broadcasts
        self._listener_task = None

    async def _listen_to_redis(self):
        await self.pubsub.subscribe("websocket_broadcast")
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                room_id = data.get("room_id")
                payload = data.get("payload")
                
                # Push safely to all connected sockets on THIS CURRENT worker!
                if room_id in self.active_connections:
                    for connection in self.active_connections[room_id]:
                        try:
                            await connection.send_json(payload)
                        except Exception:
                            # Drop silent exceptions for disconnected ghosts
                            pass

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen_to_redis())

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: dict, room_id: str):
        # Instead of sending directly manually to local connections, 
        # we publish to REDIS so EVERY worker gets it, including ourselves!
        payload = {"room_id": room_id, "payload": message}
        try:
            await self.redis_client.publish("websocket_broadcast", json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to publish to redis: {e}")

    def broadcast_sync(self, message: dict, room_id: str):
        """Used heavily by standard threading tools blocking operations."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message, room_id))
        except RuntimeError:
            asyncio.run(self.broadcast(message, room_id))

# Create a global instance
manager = ConnectionManager()
