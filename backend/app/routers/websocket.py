import asyncio
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast_json(self, message: dict):
        """
        Non-blocking concurrent broadcast to all active WebSocket clients.
        Uses asyncio.gather for parallel sub-millisecond dispatch.
        """
        if not self.active_connections:
            return

        connections = list(self.active_connections)
        results = await asyncio.gather(
            *[conn.send_json(message) for conn in connections],
            return_exceptions=True
        )

        # Prune broken / closed connections immediately
        for conn, res in zip(connections, results):
            if isinstance(res, Exception):
                self.disconnect(conn)


ws_manager = ConnectionManager()


@router.websocket("/ws/telemetry")
@router.websocket("/ws/live")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive heartbeat listener
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
