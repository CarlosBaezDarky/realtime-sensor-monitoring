"""
Sistema de semáforos para control de concurrencia en sensores
Versión mejorada con más dinamismo
"""
import threading
import asyncio
import random
import time
from typing import Dict, List, Optional, Any
from collections import deque
import logging
from datetime import datetime, timedelta  # 👈 IMPORTANTE: Agregar timedelta aquí
from enum import Enum

logger = logging.getLogger(__name__)

class SensorState(Enum):
    IDLE = "idle"
    READING = "reading"
    WRITING = "writing"
    ERROR = "error"
    BLOCKED = "blocked"
    QUEUED = "queued"

class SensorSemaphore:
    """Semáforo especializado para control de acceso a datos de sensores"""
    
    def __init__(self, sensor_id: str, max_readers: int = 5):
        self.sensor_id = sensor_id
        
        # Semáforos principales
        self.read_semaphore = threading.Semaphore(max_readers)
        self.write_semaphore = threading.Semaphore(1)
        self.resource_semaphore = threading.Semaphore(1)
        
        # Control de lectores
        self.readers_count = 0
        self.readers_lock = threading.Lock()
        
        # Control de escritores
        self.writers_waiting = 0
        self.writers_lock = threading.Lock()
        
        # Cola de datos (productor-consumidor)
        self.data_queue = deque(maxlen=50)
        self.queue_semaphore = threading.Semaphore(0)
        self.queue_mutex = threading.Lock()
        
        # Estado del sensor
        self.state = SensorState.IDLE
        self.state_lock = threading.Lock()
        self.last_update = None
        self.current_value = None
        self.read_count = 0
        self.write_count = 0
        self.error_count = 0
        
        # Historial de actividad
        self.activity_log = deque(maxlen=100)
        
    def acquire_read(self, timeout: Optional[float] = None) -> bool:
        """Adquiere permiso de lectura"""
        try:
            with self.writers_lock:
                if self.writers_waiting > 0:
                    self._log_activity(f"Esperando por escritores")
            
            acquired = self.read_semaphore.acquire(timeout=timeout)
            if not acquired:
                return False
                
            with self.readers_lock:
                self.readers_count += 1
                if self.readers_count == 1:
                    self.resource_semaphore.acquire()
                    
            with self.state_lock:
                self.state = SensorState.READING
                self.read_count += 1
                self.last_update = datetime.now()
                
            self._log_activity(f"Lectura adquirida. Lectores: {self.readers_count}")
            return True
            
        except Exception as e:
            logger.error(f"Error adquiriendo lectura: {e}")
            self.error_count += 1
            return False
    
    def release_read(self):
        """Libera permiso de lectura"""
        try:
            with self.readers_lock:
                self.readers_count -= 1
                if self.readers_count == 0:
                    self.resource_semaphore.release()
                    
            self.read_semaphore.release()
            
            with self.state_lock:
                if self.readers_count == 0:
                    self.state = SensorState.IDLE
                    
            self._log_activity(f"Lectura liberada. Lectores: {self.readers_count}")
            
        except Exception as e:
            logger.error(f"Error liberando lectura: {e}")
            self.error_count += 1
    
    def acquire_write(self, timeout: Optional[float] = None) -> bool:
        """Adquiere permiso de escritura exclusiva"""
        try:
            with self.writers_lock:
                self.writers_waiting += 1
                
            acquired = self.resource_semaphore.acquire(timeout=timeout)
            if not acquired:
                with self.writers_lock:
                    self.writers_waiting -= 1
                return False
                
            self.write_semaphore.acquire()
            
            with self.writers_lock:
                self.writers_waiting -= 1
                
            with self.state_lock:
                self.state = SensorState.WRITING
                self.write_count += 1
                self.last_update = datetime.now()
                
            self._log_activity(f"Escritura adquirida. Esperando: {self.writers_waiting}")
            return True
            
        except Exception as e:
            logger.error(f"Error adquiriendo escritura: {e}")
            self.error_count += 1
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
                
            self._log_activity("Escritura liberada")
            
        except Exception as e:
            logger.error(f"Error liberando escritura: {e}")
            self.error_count += 1
    
    def produce_data(self, data: Any) -> bool:
        """Productor: Agrega datos a la cola"""
        try:
            with self.queue_mutex:
                self.data_queue.append(data)
                self.current_value = data
                self.last_update = datetime.now()
                
            self.queue_semaphore.release()
            
            # Simular actividad de lectores después de producir
            if random.random() < 0.2:  # 20% de probabilidad
                self._simulate_readers()
                
            self._log_activity(f"Dato producido. Cola: {len(self.data_queue)}")
            return True
            
        except Exception as e:
            logger.error(f"Error produciendo datos: {e}")
            self.error_count += 1
            return False
    
    def consume_data(self, timeout: Optional[float] = None) -> Optional[Any]:
        """Consumidor: Obtiene datos de la cola"""
        try:
            acquired = self.queue_semaphore.acquire(timeout=timeout)
            if not acquired:
                return None
                
            with self.queue_mutex:
                if self.data_queue:
                    data = self.data_queue.popleft()
                    self._log_activity(f"Dato consumido. Cola: {len(self.data_queue)}")
                    return data
                return None
                
        except Exception as e:
            logger.error(f"Error consumiendo datos: {e}")
            self.error_count += 1
            return None
    
    def _simulate_readers(self):
        """Simula lectores concurrentes para generar dinamismo"""
        def reader_task(reader_id):
            if self.acquire_read(timeout=0.5):
                time.sleep(random.uniform(0.1, 0.3))
                self.release_read()
        
        num_readers = random.randint(1, 3)
        threads = []
        for i in range(num_readers):
            thread = threading.Thread(target=reader_task, args=(i,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
    
    def _log_activity(self, message: str):
        """Registra actividad en el log del sensor"""
        self.activity_log.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "state": self.state.value,
            "readers": self.readers_count,
            "writers_waiting": self.writers_waiting,
            "queue_size": len(self.data_queue)
        })
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas completas del semáforo"""
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
            "has_current_value": self.current_value is not None,
            "total_reads": self.read_count,
            "total_writes": self.write_count,
            "error_count": self.error_count,
            "recent_activity": list(self.activity_log)[-5:]  # Últimas 5 actividades
        }


class SensorSemaphoreManager:
    """Gestor global de semáforos para todos los sensores"""
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
        
        # Semáforos del sistema
        self.broadcast_semaphore = threading.Semaphore(10)
        self.db_semaphore = threading.Semaphore(3)
        self.alert_semaphore = threading.Semaphore(5)
        
        # Cola global de alertas
        self.alert_queue = deque(maxlen=100)
        self.alert_queue_semaphore = threading.Semaphore(0)
        self.alert_queue_mutex = threading.Lock()
        
        # Estadísticas del sistema
        self.total_operations = 0
        self.start_time = datetime.now()
        
        logger.info("🚦 SensorSemaphoreManager inicializado")
    
    def get_sensor_semaphore(self, sensor_id: str, max_readers: Optional[int] = None) -> SensorSemaphore:
        """Obtiene o crea un semáforo para un sensor específico"""
        with self.semaphore_lock:
            if sensor_id not in self.sensor_semaphores:
                from config import settings
                max_r = max_readers or settings.MAX_CONCURRENT_READERS
                self.sensor_semaphores[sensor_id] = SensorSemaphore(sensor_id, max_r)
                logger.info(f"🚦 Semáforo creado para sensor {sensor_id}")
                
            return self.sensor_semaphores[sensor_id]
    
    def acquire_db(self, timeout: Optional[float] = None) -> bool:
        """Adquiere permiso para operación de base de datos"""
        self.total_operations += 1
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
        uptime = (datetime.now() - self.start_time).total_seconds()
        
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
            "total_sensors": len(self.sensor_semaphores),
            "total_operations": self.total_operations,
            "uptime_seconds": round(uptime, 2),
            "uptime_formatted": str(timedelta(seconds=int(uptime)))  # 👈 Ahora timedelta está definido
        }


# Instancia global
sensor_semaphore_manager = SensorSemaphoreManager()