from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.WebSocketManager import manager
import json

router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            # We use receive_text and parse rather than receive_json to handle bad formats gracefully
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                message_type = data.get("type")
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message_type == "ai_prompt":
                    pass
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
