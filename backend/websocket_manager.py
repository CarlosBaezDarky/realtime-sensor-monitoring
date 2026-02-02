"""
Gestión de conexiones WebSocket
"""
import asyncio
import json
from typing import Dict, Set, List
from datetime import datetime, timezone

from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[WebSocket, Dict] = {}
        self.sensor_subscriptions: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, channel: str = "sensors"):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_data[websocket] = {
            "connected_at": datetime.now(timezone.utc),
            "channel": channel,
            "subscribed_sensors": set()
        }
        
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if websocket in self.connection_data:
            # Remover de suscripciones
            for sensor_id in self.connection_data[websocket]["subscribed_sensors"]:
                if sensor_id in self.sensor_subscriptions:
                    self.sensor_subscriptions[sensor_id].discard(websocket)
            
            del self.connection_data[websocket]
    
    def subscribe_sensor(self, websocket: WebSocket, sensor_id: str):
        if websocket in self.connection_data:
            self.connection_data[websocket]["subscribed_sensors"].add(sensor_id)
            
            if sensor_id not in self.sensor_subscriptions:
                self.sensor_subscriptions[sensor_id] = set()
            self.sensor_subscriptions[sensor_id].add(websocket)
    
    def unsubscribe_sensor(self, websocket: WebSocket, sensor_id: str):
        if websocket in self.connection_data:
            self.connection_data[websocket]["subscribed_sensors"].discard(sensor_id)
            
            if sensor_id in self.sensor_subscriptions:
                self.sensor_subscriptions[sensor_id].discard(websocket)
    
    async def broadcast_sensor_data(self, data: Dict):
        """
        Broadcast de datos de sensores a todos los clientes
        """
        if not self.active_connections:
            return
        
        message = {
            "type": "sensor_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)
        
        # Limpiar conexiones desconectadas
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_alerts(self, alerts: List[Dict]):
        """
        Broadcast de alertas a clientes suscritos
        """
        if not alerts:
            return
        
        message = {
            "type": "alert",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alerts": alerts
        }
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            conn_data = self.connection_data.get(connection)
            if conn_data and conn_data["channel"] == "alerts":
                try:
                    await connection.send_text(message_json)
                except Exception:
                    disconnected.append(connection)
        
        # Limpiar conexiones desconectadas
        for connection in disconnected:
            self.disconnect(connection)
    
    def get_connection_count(self) -> Dict:
        """
        Obtener estadísticas de conexiones
        """
        channels = {}
        for conn_data in self.connection_data.values():
            channel = conn_data["channel"]
            channels[channel] = channels.get(channel, 0) + 1
        
        return {
            "total": len(self.active_connections),
            "by_channel": channels,
            "subscriptions": {
                sensor_id: len(sockets)
                for sensor_id, sockets in self.sensor_subscriptions.items()
            }
        }