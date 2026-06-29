"""WebSocket routes — real-time log streaming.

Mounted at /ws prefix by create_app().
"""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log = logging.getLogger(__name__)


class LogBroadcaster:
    """Manages WebSocket connections and broadcasts log entries.

    Supports multiple concurrent clients. Connection list operations are
    safe because async WebSocket handlers are single-threaded per event loop.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, entry: dict[str, Any]) -> None:
        """Broadcast a log entry to all connected clients."""
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(entry)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Module-level singleton
_broadcaster: LogBroadcaster | None = None


def get_broadcaster() -> LogBroadcaster:
    """Get the global LogBroadcaster singleton."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = LogBroadcaster()
    return _broadcaster


def reset_broadcaster() -> None:
    """Reset the broadcaster (for testing)."""
    global _broadcaster
    _broadcaster = None


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time log streaming.

    Clients connect here and receive log entries as JSON messages.
    """
    broadcaster = get_broadcaster()
    await broadcaster.connect(websocket)
    try:
        # Send a welcome message
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Connected to forge-agent log stream",
            }
        )
        # Keep connection alive, listen for client messages (e.g. filter commands)
        while True:
            data = await websocket.receive_text()
            # Echo back any received text as acknowledgment
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)
