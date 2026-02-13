"""
Sistema de semáforos para control de concurrencia en sensores
Implementa patrones productor-consumidor y lectores-escritores
"""
import threading
import asyncio
from typing import Dict, List, Optional, Any
from collections import deque
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class SensorState(Enum):
    """Estados posibles de un sensor"""
    IDLE = "idle"
    READING = "reading"
    WRITING = "writing"
    ERROR = "error"
    BLOCKED = "blocked"

class SensorSemaphore:
    """
    Semáforo especializado para control de acceso a datos de sensores
    Implementa el problema lectores-escritores con prioridad para escritores
    """
    
    def __init__(self, sensor_id: str, max_readers: int = 5):
        self.sensor_id = sensor_id
        
        # 🚦 SEMÁFOROS PRINCIPALES
        self.read_semaphore = threading.Semaphore(max_readers)  # Lectores concurrentes
        self.write_semaphore = threading.Semaphore(1)           # Escritura exclusiva (mutex)
        self.resource_semaphore = threading.Semaphore(1)        # Protección del recurso
        
        # Control de lectores
        self.readers_count = 0
        self.readers_lock = threading.Lock()
        
        # Control de escritores
        self.writers_waiting = 0
        self.writers_lock = threading.Lock()
        
        # Cola de datos con semáforo productor-consumidor
        self.data_queue = deque(maxlen=20)
        self.queue_semaphore = threading.Semaphore(0)  # Inicia en 0 (consumidores esperan)
        self.queue_mutex = threading.Lock()
        
        # Estado del sensor
        self.state = SensorState.IDLE
        self.state_lock = threading.Lock()
        self.last_update = None
        self.current_value = None
        
    def acquire_read(self, timeout: Optional[float] = None) -> bool:
        """
        Adquiere permiso de lectura
        Retorna: True si se adquirió el permiso, False si timeout
        """
        try:
            # Los escritores tienen prioridad
            with self.writers_lock:
                if self.writers_waiting > 0:
                    logger.debug(f"Sensor {self.sensor_id}: Esperando por escritores")
            
            # Adquirir semáforo de lectura
            acquired = self.read_semaphore.acquire(timeout=timeout)
            if not acquired:
                return False
                
            with self.readers_lock:
                self.readers_count += 1
                if self.readers_count == 1:
                    # Primer lector bloquea escritores
                    self.resource_semaphore.acquire()
                    
            with self.state_lock:
                self.state = SensorState.READING
                
            return True
            
        except Exception as e:
            logger.error(f"Error adquiriendo lectura sensor {self.sensor_id}: {e}")
            return False
    
    def release_read(self):
        """Libera permiso de lectura"""
        try:
            with self.readers_lock:
                self.readers_count -= 1
                if self.readers_count == 0:
                    # Último lector libera escritores
                    self.resource_semaphore.release()
                    
            self.read_semaphore.release()
            
            with self.state_lock:
                if self.readers_count == 0:
                    self.state = SensorState.IDLE
                    
        except Exception as e:
            logger.error(f"Error liberando lectura sensor {self.sensor_id}: {e}")
    
    def acquire_write(self, timeout: Optional[float] = None) -> bool:
        """
        Adquiere permiso de escritura exclusiva
        Retorna: True si se adquirió el permiso
        """
        try:
            # Anunciar escritor esperando
            with self.writers_lock:
                self.writers_waiting += 1
                
            # Adquirir semáforo de recurso (espera a lectores)
            acquired = self.resource_semaphore.acquire(timeout=timeout)
            if not acquired:
                with self.writers_lock:
                    self.writers_waiting -= 1
                return False
                
            # Adquirir semáforo de escritura
            self.write_semaphore.acquire()
            
            with self.writers_lock:
                self.writers_waiting -= 1
                
            with self.state_lock:
                self.state = SensorState.WRITING
                
            return True
            
        except Exception as e:
            logger.error(f"Error adquiriendo escritura sensor {self.sensor_id}: {e}")
            with self.writers_lock:
                self.writers_waiting -= 1
            return False
    
    def release_write(self):
        """Libera permiso de escritura"""
        try:
            self.write_semaphore.release()
            self.resource_semaphore.release()
            
            with self.state_lock:
                self.state = SensorState.IDLE
                
        except Exception as e:
            logger.error(f"Error liberando escritura sensor {self.sensor_id}: {e}")
    
    # Métodos productor-consumidor para cola de datos
    
    def produce_data(self, data: Any) -> bool:
        """
        Productor: Agrega datos a la cola
        """
        try:
            with self.queue_mutex:
                self.data_queue.append(data)
                self.last_update = datetime.utcnow()
                self.current_value = data
                
            # Señalizar que hay datos disponibles
            self.queue_semaphore.release()
            return True
            
        except Exception as e:
            logger.error(f"Error produciendo datos sensor {self.sensor_id}: {e}")
            return False
    
    def consume_data(self, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Consumidor: Obtiene datos de la cola
        Espera si no hay datos disponibles (semáforo en 0)
        """
        try:
            # Esperar por datos (semáforo productor-consumidor)
            acquired = self.queue_semaphore.acquire(timeout=timeout)
            if not acquired:
                return None
                
            with self.queue_mutex:
                if self.data_queue:
                    return self.data_queue.popleft()
                return None
                
        except Exception as e:
            logger.error(f"Error consumiendo datos sensor {self.sensor_id}: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del semáforo del sensor"""
        return {
            "sensor_id": self.sensor_id,
            "state": self.state.value,
            "readers_count": self.readers_count,
            "writers_waiting": self.writers_waiting,
            "read_semaphore_value": self.read_semaphore._value,
            "write_semaphore_value": self.write_semaphore._value,
            "queue_size": len(self.data_queue),
            "queue_semaphore_value": self.queue_semaphore._value,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "has_current_value": self.current_value is not None
        }


class SensorSemaphoreManager:
    """
    Gestor global de semáforos para todos los sensores
    Implementa patrón Singleton
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.sensor_semaphores: Dict[str, SensorSemaphore] = {}
        self.semaphore_lock = threading.RLock()
        
        # 🚦 SEMÁFOROS DEL SISTEMA
        self.broadcast_semaphore = threading.Semaphore(10)  # Broadcasts simultáneos
        self.db_semaphore = threading.Semaphore(3)          # Conexiones DB simultáneas
        self.alert_semaphore = threading.Semaphore(5)       # Procesamiento de alertas
        
        # Cola global de alertas (productor-consumidor)
        self.alert_queue = deque(maxlen=50)
        self.alert_queue_semaphore = threading.Semaphore(0)
        self.alert_queue_mutex = threading.Lock()
        
        logger.info("🚦 SensorSemaphoreManager inicializado")
    
    def get_sensor_semaphore(self, sensor_id: str, max_readers: Optional[int] = None) -> SensorSemaphore:
        """
        Obtiene o crea un semáforo para un sensor específico
        """
        with self.semaphore_lock:
            if sensor_id not in self.sensor_semaphores:
                from config import settings
                max_r = max_readers or settings.MAX_CONCURRENT_READERS
                self.sensor_semaphores[sensor_id] = SensorSemaphore(sensor_id, max_r)
                logger.info(f"🚦 Semáforo creado para sensor {sensor_id}")
                
            return self.sensor_semaphores[sensor_id]
    
    def acquire_db(self, timeout: Optional[float] = None) -> bool:
        """Adquiere permiso para operación de base de datos"""
        return self.db_semaphore.acquire(timeout=timeout)
    
    def release_db(self):
        """Libera permiso de base de datos"""
        self.db_semaphore.release()
    
    def acquire_broadcast(self, timeout: Optional[float] = None) -> bool:
        """Adquiere permiso para broadcast WebSocket"""
        return self.broadcast_semaphore.acquire(timeout=timeout)
    
    def release_broadcast(self):
        """Libera permiso de broadcast"""
        self.broadcast_semaphore.release()
    
    def produce_alert(self, alert_data: Dict) -> bool:
        """Productor: Agrega alerta a la cola global"""
        try:
            with self.alert_queue_mutex:
                self.alert_queue.append(alert_data)
            self.alert_queue_semaphore.release()
            return True
        except Exception as e:
            logger.error(f"Error produciendo alerta: {e}")
            return False
    
    def consume_alert(self, timeout: Optional[float] = None) -> Optional[Dict]:
        """Consumidor: Obtiene alerta de la cola global"""
        try:
            acquired = self.alert_queue_semaphore.acquire(timeout=timeout)
            if not acquired:
                return None
                
            with self.alert_queue_mutex:
                if self.alert_queue:
                    return self.alert_queue.popleft()
                return None
        except Exception as e:
            logger.error(f"Error consumiendo alerta: {e}")
            return None
    
    def get_system_stats(self) -> Dict:
        """Obtiene estadísticas de todos los semáforos del sistema"""
        return {
            "sensors": {
                sensor_id: sem.get_stats()
                for sensor_id, sem in self.sensor_semaphores.items()
            },
            "system_semaphores": {
                "broadcast_semaphore": self.broadcast_semaphore._value,
                "db_semaphore": self.db_semaphore._value,
                "alert_semaphore": self.alert_semaphore._value,
                "alert_queue_size": len(self.alert_queue),
                "alert_queue_semaphore": self.alert_queue_semaphore._value
            },
            "total_sensors": len(self.sensor_semaphores)
        }


# Instancia global del gestor de semáforos
sensor_semaphore_manager = SensorSemaphoreManager()