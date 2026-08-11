import asyncio
import logging
from typing import Optional

from fastapi import WebSocket
import orjson

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        data = orjson.dumps(message).decode()
        disconnected = []
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(data)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        try:
            data = orjson.dumps(message).decode()
            await websocket.send_text(data)
        except Exception:
            await self.disconnect(websocket)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


ws_manager = ConnectionManager()
