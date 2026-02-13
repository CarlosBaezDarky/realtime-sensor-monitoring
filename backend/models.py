"""
Modelos de datos con soporte para semáforos
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime as dt
from typing import Optional as Opt

Base = declarative_base()

class SensorData(Base):
    """
    Modelo para almacenar datos de sensores
    """
    __tablename__ = "sensor_data"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sensor_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Mediciones
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    
    # Metadatos adicionales
    location = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    
    # Para análisis posterior
    is_anomaly = Column(Boolean, default=False)
    
    # 🚦 NUEVOS CAMPOS PARA SEMÁFOROS
    processing_time = Column(Float, nullable=True)  # Tiempo de procesamiento en ms
    queue_wait_time = Column(Float, nullable=True)  # Tiempo en cola
    semaphore_acquired = Column(Boolean, default=True)  # Si se adquirió semáforo
    
    def __repr__(self):
        return f"<SensorData(sensor_id='{self.sensor_id}', temp={self.temperature})>"


class Alert(Base):
    """
    Modelo para almacenar alertas generadas
    """
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sensor_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Información de la alerta
    alert_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    severity = Column(String, default="medium")
    
    # Valores que dispararon la alerta
    threshold_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    
    # Estado de la alerta
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    
    # Para notificaciones
    notified = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime, nullable=True)
    
    # 🚦 CAMPOS PARA SEMÁFOROS
    queue_position = Column(Integer, nullable=True)  # Posición en cola de alertas
    processing_delay = Column(Float, nullable=True)  # Delay de procesamiento
    
    def __repr__(self):
        return f"<Alert(sensor_id='{self.sensor_id}', type='{self.alert_type}')>"


class SensorSemaphoreStats(Base):
    """
    🚦 NUEVO MODELO: Estadísticas de semáforos para monitoreo
    """
    __tablename__ = "semaphore_stats"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    sensor_id = Column(String, index=True, nullable=True)
    
    # Estadísticas de semáforo
    semaphore_type = Column(String, nullable=False)  # read, write, queue, broadcast
    semaphore_value = Column(Integer, nullable=False)
    readers_count = Column(Integer, default=0)
    writers_waiting = Column(Integer, default=0)
    queue_size = Column(Integer, default=0)
    
    # Métricas de rendimiento
    avg_wait_time_ms = Column(Float, nullable=True)
    max_concurrent = Column(Integer, nullable=True)
    total_operations = Column(Integer, default=0)


# MODELOS PYDANTIC PARA VALIDACIÓN
class SensorDataCreate(BaseModel):
    sensor_id: str
    temperature: Opt[float] = None
    humidity: Opt[float] = None
    pressure: Opt[float] = None
    location: Opt[str] = None
    device_type: Opt[str] = None
    
    # 🚦 Campos opcionales para semáforos
    queue_wait_time: Opt[float] = None

class SensorDataResponse(SensorDataCreate):
    id: int
    timestamp: dt
    is_anomaly: bool
    processing_time: Opt[float] = None
    
    class Config:
        from_attributes = True

class AlertCreate(BaseModel):
    sensor_id: str
    alert_type: str
    message: str
    severity: Opt[str] = "medium"
    threshold_value: Opt[float] = None
    actual_value: Opt[float] = None

class AlertResponse(AlertCreate):
    id: int
    timestamp: dt
    is_resolved: bool
    notified: bool
    queue_position: Opt[int] = None
    
    class Config:
        from_attributes = True

# 🚦 NUEVO MODELO: Estado de semáforos para API
class SemaphoreStatusResponse(BaseModel):
    sensor_id: str
    state: str
    readers_count: int
    writers_waiting: int
    read_semaphore_value: int
    write_semaphore_value: int
    queue_size: int
    queue_semaphore_value: int
    last_update: Opt[str] = None

class SystemSemaphoreStatsResponse(BaseModel):
    sensors: Dict[str, Any]
    system_semaphores: Dict[str, int]
    total_sensors: int