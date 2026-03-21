"""
WebSocket manager for real-time notifications.

Provides live push notifications to connected clients.
"""

from typing import Dict, Set
from fastapi import WebSocket
from datetime import datetime
import json
import asyncio

from utils.logger import logger


class ConnectionManager:
    """
    Manages WebSocket connections for real-time notifications.
    
    Features:
    - Per-user connections (multiple devices supported)
    - Automatic reconnection handling
    - Message queuing for offline users (optional)
    """
    
    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self._active_connections: Dict[str, Set[WebSocket]] = {}
        # Optional: Message queue for offline users (last N messages)
        self._message_queue: Dict[str, list] = {}
        self._max_queued_messages = 50
    
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self._active_connections:
            self._active_connections[user_id] = set()
        
        self._active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected: user_id={user_id}, total_connections={len(self._active_connections[user_id])}")
        
        # Send any queued messages
        await self._flush_queue(user_id, websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a WebSocket connection."""
        if user_id in self._active_connections:
            self._active_connections[user_id].discard(websocket)
            if not self._active_connections[user_id]:
                del self._active_connections[user_id]
        logger.info(f"WebSocket disconnected: user_id={user_id}")
    
    def is_connected(self, user_id: str) -> bool:
        """Check if user has any active connections."""
        return user_id in self._active_connections and len(self._active_connections[user_id]) > 0
    
    def get_connection_count(self, user_id: str = None) -> int:
        """Get total connection count or count for specific user."""
        if user_id:
            return len(self._active_connections.get(user_id, set()))
        return sum(len(conns) for conns in self._active_connections.values())
    
    async def send_personal(self, user_id: str, message: dict) -> int:
        """
        Send message to a specific user's all connections.
        
        Returns:
            Number of connections message was sent to
        """
        sent_count = 0
        
        if user_id in self._active_connections:
            disconnected = set()
            
            for connection in self._active_connections[user_id]:
                try:
                    await connection.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send to user {user_id}: {e}")
                    disconnected.add(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                self._active_connections[user_id].discard(conn)
        else:
            # Queue message for offline user
            self._queue_message(user_id, message)
        
        return sent_count
    
    async def broadcast(self, message: dict, exclude_users: set = None) -> int:
        """
        Broadcast message to all connected users.
        
        Returns:
            Number of users message was sent to
        """
        exclude_users = exclude_users or set()
        sent_count = 0
        
        for user_id in list(self._active_connections.keys()):
            if user_id not in exclude_users:
                count = await self.send_personal(user_id, message)
                if count > 0:
                    sent_count += 1
        
        return sent_count
    
    def _queue_message(self, user_id: str, message: dict) -> None:
        """Queue a message for an offline user."""
        if user_id not in self._message_queue:
            self._message_queue[user_id] = []
        
        message["queued_at"] = datetime.utcnow().isoformat()
        self._message_queue[user_id].append(message)
        
        # Trim queue to max size
        if len(self._message_queue[user_id]) > self._max_queued_messages:
            self._message_queue[user_id] = self._message_queue[user_id][-self._max_queued_messages:]
    
    async def _flush_queue(self, user_id: str, websocket: WebSocket) -> None:
        """Send queued messages to newly connected user."""
        if user_id in self._message_queue:
            messages = self._message_queue.pop(user_id, [])
            for message in messages:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to flush queue for {user_id}: {e}")
                    break
    
    def get_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "total_users_connected": len(self._active_connections),
            "total_connections": self.get_connection_count(),
            "queued_messages": sum(len(q) for q in self._message_queue.values()),
            "users_with_queued_messages": len(self._message_queue),
        }


# Global connection manager instance
ws_manager = ConnectionManager()


async def push_notification(
    recipient_id: str,
    event_type: str,
    message: str,
    related_id: str = None,
    context: dict = None,
) -> int:
    """
    Push a real-time notification to a user.
    
    This should be called after create_notification() to send live updates.
    
    Returns:
        Number of connections notified
    """
    notification = {
        "type": "notification",
        "event_type": event_type,
        "message": message,
        "related_id": related_id,
        "context": context or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    return await ws_manager.send_personal(recipient_id, notification)
