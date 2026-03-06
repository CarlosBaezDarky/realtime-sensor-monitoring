"""
Sistema de excepciones personalizadas para el monitoreo de sensores
"""
import traceback
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================
# EXCEPCIONES PERSONALIZADAS
# ============================================

class SensorBaseException(Exception):
    """Excepción base para todo el sistema de sensores"""
    def __init__(self, message: str, sensor_id: Optional[str] = None, severity: str = "medium"):
        self.message = message
        self.sensor_id = sensor_id
        self.severity = severity
        self.timestamp = datetime.now()
        self.traceback = traceback.format_exc()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "sensor_id": self.sensor_id,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback
        }

class SensorConnectionError(SensorBaseException):
    """Error de conexión con el sensor"""
    def __init__(self, sensor_id: str, reason: str = "timeout"):
        super().__init__(
            message=f"🔌 Error de conexión con sensor {sensor_id}: {reason}",
            sensor_id=sensor_id,
            severity="critical"
        )
        self.reason = reason

class SensorDataError(SensorBaseException):
    """Error en los datos del sensor (valores fuera de rango)"""
    def __init__(self, sensor_id: str, value: float, expected_range: str):
        super().__init__(
            message=f"📊 Dato inválido en sensor {sensor_id}: {value} (rango esperado: {expected_range})",
            sensor_id=sensor_id,
            severity="high"
        )
        self.value = value
        self.expected_range = expected_range

class SensorCalibrationError(SensorBaseException):
    """Error de calibración del sensor"""
    def __init__(self, sensor_id: str, calibration_factor: float):
        super().__init__(
            message=f"⚙️ Error de calibración en sensor {sensor_id}: factor {calibration_factor} fuera de rango",
            sensor_id=sensor_id,
            severity="high"
        )
        self.calibration_factor = calibration_factor

class DatabaseError(SensorBaseException):
    """Error de base de datos"""
    def __init__(self, operation: str, details: str):
        super().__init__(
            message=f"💾 Error de base de datos en {operation}: {details}",
            severity="critical"
        )
        self.operation = operation
        self.details = details

class WebSocketError(SensorBaseException):
    """Error en conexión WebSocket"""
    def __init__(self, client_id: str, reason: str):
        super().__init__(
            message=f"📡 Error WebSocket cliente {client_id}: {reason}",
            severity="medium"
        )
        self.client_id = client_id

class SemaphoreTimeoutError(SensorBaseException):
    """Timeout en adquisición de semáforo"""
    def __init__(self, sensor_id: str, semaphore_type: str, timeout: float):
        super().__init__(
            message=f"⏱️ Timeout en semáforo {semaphore_type} para sensor {sensor_id} ({timeout}s)",
            sensor_id=sensor_id,
            severity="high"
        )
        self.semaphore_type = semaphore_type
        self.timeout = timeout

class AlertQueueFullError(SensorBaseException):
    """Cola de alertas llena"""
    def __init__(self, queue_size: int):
        super().__init__(
            message=f"⚠️ Cola de alertas llena ({queue_size} items). Descartando alerta más antigua",
            severity="medium"
        )
        self.queue_size = queue_size

# ============================================
# GESTOR DE EXCEPCIONES
# ============================================

class ExceptionManager:
    """Singleton que gestiona todas las excepciones del sistema"""
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
        self.exception_history = []
        self.active_exceptions = []
        self.exception_counters = {
            "SensorConnectionError": 0,
            "SensorDataError": 0,
            "SensorCalibrationError": 0,
            "DatabaseError": 0,
            "WebSocketError": 0,
            "SemaphoreTimeoutError": 0,
            "AlertQueueFullError": 0,
            "Other": 0
        }
        self.max_history = 100
        self.exception_lock = threading.Lock()
        self.exception_semaphore = threading.Semaphore(5)  # Límite de procesamiento
        
        logger.info("📋 ExceptionManager inicializado")
    
    def register_exception(self, exception: SensorBaseException) -> Dict[str, Any]:
        """Registra una excepción en el sistema"""
        with self.exception_lock:
            exception_dict = exception.to_dict()
            exception_dict["id"] = len(self.exception_history) + 1
            exception_dict["resolved"] = False
            exception_dict["resolved_at"] = None
            
            # Agregar al historial
            self.exception_history.append(exception_dict)
            if len(self.exception_history) > self.max_history:
                self.exception_history.pop(0)
            
            # Agregar a activas si es crítica o alta
            if exception.severity in ["critical", "high"]:
                self.active_exceptions.append(exception_dict)
                if len(self.active_exceptions) > 20:  # Máximo 20 activas
                    self.active_exceptions.pop(0)
            
            # Actualizar contador
            exc_type = exception.__class__.__name__
            if exc_type in self.exception_counters:
                self.exception_counters[exc_type] += 1
            else:
                self.exception_counters["Other"] += 1
            
            logger.warning(f"⚠️ Excepción registrada: {exception.message}")
            
            return exception_dict
    
    def resolve_exception(self, exception_id: int) -> bool:
        """Marca una excepción como resuelta"""
        with self.exception_lock:
            for exc in self.exception_history:
                if exc["id"] == exception_id:
                    exc["resolved"] = True
                    exc["resolved_at"] = datetime.now().isoformat()
                    
                    # Remover de activas
                    self.active_exceptions = [e for e in self.active_exceptions if e["id"] != exception_id]
                    
                    logger.info(f"✅ Excepción {exception_id} resuelta")
                    return True
            return False
    
    def get_exception_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de excepciones"""
        with self.exception_lock:
            return {
                "total_exceptions": len(self.exception_history),
                "active_exceptions": len(self.active_exceptions),
                "counters": self.exception_counters.copy(),
                "by_severity": {
                    "critical": sum(1 for e in self.exception_history if e["severity"] == "critical"),
                    "high": sum(1 for e in self.exception_history if e["severity"] == "high"),
                    "medium": sum(1 for e in self.exception_history if e["severity"] == "medium"),
                    "low": sum(1 for e in self.exception_history if e["severity"] == "low")
                },
                "recent": self.exception_history[-5:] if self.exception_history else []
            }
    
    def simulate_random_exception(self) -> Optional[Dict[str, Any]]:
        """Simula una excepción aleatoria para pruebas"""
        exception_types = [
            (SensorConnectionError, ["sensor_001", "sensor_002", "sensor_003"], ["timeout", "refused", "unreachable"]),
            (SensorDataError, ["sensor_004", "sensor_005"], [150.0, -50.0, 9999.0], ["0-100", "-20-50", "0-2000"]),
            (SensorCalibrationError, ["sensor_006", "sensor_007"], [2.5, 0.1, 5.0]),
            (SemaphoreTimeoutError, ["sensor_001", "sensor_003", "sensor_005"], ["read", "write", "queue"], [2.0, 5.0, 10.0]),
            (AlertQueueFullError, [], [50])
        ]
        
        if random.random() < 0.3:  # 30% de probabilidad
            exc_type, *params = random.choice(exception_types)
            
            if exc_type == SensorConnectionError:
                sensor = random.choice(params[0])
                reason = random.choice(params[1])
                return self.register_exception(exc_type(sensor, reason))
            
            elif exc_type == SensorDataError:
                sensor = random.choice(params[0])
                value = random.choice(params[1])
                range_str = random.choice(params[2])
                return self.register_exception(exc_type(sensor, value, range_str))
            
            elif exc_type == SensorCalibrationError:
                sensor = random.choice(params[0])
                factor = random.choice(params[1])
                return self.register_exception(exc_type(sensor, factor))
            
            elif exc_type == SemaphoreTimeoutError:
                sensor = random.choice(params[0])
                sem_type = random.choice(params[1])
                timeout = random.choice(params[2])
                return self.register_exception(exc_type(sensor, sem_type, timeout))
            
            elif exc_type == AlertQueueFullError:
                size = random.choice(params[0])
                return self.register_exception(exc_type(size))
        
        return None

# Instancia global
exception_manager = ExceptionManager()