"""WebSocket manager for real-time updates across all clients."""
import asyncio
import json
from typing import Dict, Set, Any
from datetime import datetime
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages."""
    
    def __init__(self):
        # Store connections by channel/topic
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "all": set(),
            "inventory": set(),
            "sales": set(),
            "analytics": set(),
            "mobile_app": set(),  # Special channel for mobile app
        }
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            # Add to specific channel
            if channel in self.active_connections:
                self.active_connections[channel].add(websocket)
            # Always add to 'all' channel
            self.active_connections["all"].add(websocket)
        
        logger.info(f"New WebSocket connection on channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """Remove a WebSocket connection."""
        # Use synchronous removal since we might be called from non-async context
        for ch in self.active_connections.values():
            ch.discard(websocket)
        
        logger.info(f"WebSocket disconnected from channel: {channel}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict, channel: str = "all"):
        """Broadcast a message to all connections in a channel."""
        async with self._lock:
            disconnected = set()
            
            if channel == "all":
                # Broadcast to all channels
                target_connections = set()
                for conns in self.active_connections.values():
                    target_connections.update(conns)
            else:
                target_connections = self.active_connections.get(channel, set())
            
            for connection in target_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to connection: {e}")
                    disconnected.add(connection)
            
            # Clean up disconnected clients
            for conn in disconnected:
                self.disconnect(conn)
    
    async def broadcast_stock_update(self, product_id: int, product_name: str, 
                                    old_stock: int, new_stock: int, channel: str):
        """Broadcast stock update to all connected clients."""
        message = {
            "type": "stock_update",
            "data": {
                "product_id": product_id,
                "product_name": product_name,
                "old_stock": old_stock,
                "new_stock": new_stock,
                "channel": channel,
                "is_out_of_stock": new_stock <= 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message, "inventory")
        await self.broadcast(message, "all")
        
        # Special broadcast for mobile app
        await self.broadcast(message, "mobile_app")
    
    async def broadcast_sale_created(self, sale_data: dict):
        """Broadcast new sale event to all connected clients."""
        message = {
            "type": "sale_created",
            "data": sale_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message, "sales")
        await self.broadcast(message, "all")
        await self.broadcast(message, "mobile_app")
    
    async def broadcast_analytics_update(self, analytics_data: dict):
        """Broadcast analytics update to dashboard clients."""
        message = {
            "type": "analytics_update",
            "data": analytics_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message, "analytics")
        await self.broadcast(message, "all")


# Global manager instance
manager = ConnectionManager()
