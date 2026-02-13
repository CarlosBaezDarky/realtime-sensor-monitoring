"""
Gestor de conexiones WebSocket con control de concurrencia mediante semáforos
"""
import asyncio
import threading
from typing import Dict, List, Set, Optional
from fastapi import WebSocket
import logging
from datetime import datetime
from collections import defaultdict

from sensor_semaphore import sensor_semaphore_manager

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Gestor de conexiones WebSocket con semáforos para control de concurrencia
    """
    
    def __init__(self):
        # Conexiones activas
        self.active_connections: List[WebSocket] = []
        self.connections_lock = threading.Lock()
        
        # Suscripciones por sensor
        self.sensor_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.subscriptions_lock = threading.Lock()
        
        # Canales especiales
        self.alert_channels: Set[WebSocket] = set()
        
        logger.info("📡 WebSocketManager inicializado")
    
    async def connect(self, websocket: WebSocket, channel: Optional[str] = None):
        """
        Establece conexión WebSocket
        """
        await websocket.accept()
        
        with self.connections_lock:
            self.active_connections.append(websocket)
        
        if channel == "alerts":
            self.alert_channels.add(websocket)
            
        logger.info(f"Cliente conectado. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """
        Cierra conexión WebSocket
        """
        with self.connections_lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        
        # Limpiar suscripciones
        with self.subscriptions_lock:
            for sensor_id in list(self.sensor_subscriptions.keys()):
                if websocket in self.sensor_subscriptions[sensor_id]:
                    self.sensor_subscriptions[sensor_id].remove(websocket)
        
        self.alert_channels.discard(websocket)
        logger.info(f"Cliente desconectado. Total: {len(self.active_connections)}")
    
    def subscribe_sensor(self, websocket: WebSocket, sensor_id: str):
        """
        Suscribe un cliente a un sensor específico
        """
        with self.subscriptions_lock:
            self.sensor_subscriptions[sensor_id].add(websocket)
            logger.info(f"Cliente suscrito a sensor {sensor_id}")
    
    async def broadcast_sensor_data(self, data: dict):
        """
        Envía datos de sensor a todos los clientes suscritos
        Con control de semáforo para broadcasts simultáneos
        """
        sensor_id = data.get("sensor_id")
        if not sensor_id:
            return
        
        # Adquirir semáforo de broadcast
        acquired = sensor_semaphore_manager.acquire_broadcast(timeout=1)
        if not acquired:
            logger.warning("Broadcast semáforo no disponible, encolando...")
            # Aquí podrías implementar una cola de broadcast
        
        try:
            subscribers = []
            with self.subscriptions_lock:
                subscribers = list(self.sensor_subscriptions.get(sensor_id, set()))
            
            # Enviar a todos los suscriptores del sensor
            for subscriber in subscribers:
                try:
                    await subscriber.send_json({
                        "type": "sensor_data",
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error enviando a suscriptor: {e}")
            
            # También enviar a todos los clientes generales
            with self.connections_lock:
                for connection in self.active_connections:
                    try:
                        await connection.send_json({
                            "type": "sensor_data",
                            "data": data,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error en broadcast: {e}")
                        
        finally:
            # Liberar semáforo
            sensor_semaphore_manager.release_broadcast()
    
    async def broadcast_alerts(self, alerts: List[dict]):
        """
        Envía alertas a todos los clientes en canal de alertas
        Implementa patrón productor-consumidor con semáforos
        """
        # Producir alertas en la cola global
        for alert in alerts:
            sensor_semaphore_manager.produce_alert(alert)
        
        # Adquirir semáforo de alertas
        acquired = sensor_semaphore_manager.alert_semaphore.acquire(timeout=1)
        if not acquired:
            logger.warning("Semáforo de alertas no disponible")
            return
        
        try:
            # Enviar a canal de alertas
            for client in self.alert_channels:
                try:
                    await client.send_json({
                        "type": "alert",
                        "alerts": alerts,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error enviando alerta: {e}")
            
            # También enviar a todos los clientes
            with self.connections_lock:
                for connection in self.active_connections:
                    try:
                        await connection.send_json({
                            "type": "alert",
                            "alerts": alerts,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error en broadcast alertas: {e}")
                        
        finally:
            sensor_semaphore_manager.alert_semaphore.release()
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Envía mensaje personalizado a un cliente específico
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error enviando mensaje personal: {e}")
    
    def get_connection_count(self) -> int:
        """Retorna número de conexiones activas"""
        with self.connections_lock:
            return len(self.active_connections)


# Instancia global
ws_manager = WebSocketManager()