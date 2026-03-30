from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        # Maps room_id to a list of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Ignore errors if a connection drops unexpectedly
                    pass

    def broadcast_sync(self, message: dict, room_id: str):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message, room_id))
        except RuntimeError:
            asyncio.run(self.broadcast(message, room_id))


# Create a global instance to be used across the application
manager = ConnectionManager()
