from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional

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
    temperature = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    
    # Metadatos adicionales
    location = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    
    # Para análisis posterior
    is_anomaly = Column(Boolean, default=False)
    
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
    alert_type = Column(String, nullable=False)  # Ej: "high_temperature", "low_humidity"
    message = Column(String, nullable=False)
    severity = Column(String, default="medium")  # low, medium, high, critical
    
    # Valores que dispararon la alerta
    threshold_value = Column(Float)
    actual_value = Column(Float)
    
    # Estado de la alerta
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    
    # Para notificaciones
    notified = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Alert(sensor_id='{self.sensor_id}', type='{self.alert_type}')>"


# Si también necesitas modelos Pydantic para validación de entrada/salida
from pydantic import BaseModel
from datetime import datetime as dt
from typing import Optional as Opt

class SensorDataCreate(BaseModel):
    sensor_id: str
    temperature: Opt[float] = None
    humidity: Opt[float] = None
    pressure: Opt[float] = None
    location: Opt[str] = None
    device_type: Opt[str] = None

class SensorDataResponse(SensorDataCreate):
    id: int
    timestamp: dt
    is_anomaly: bool
    
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
    
    class Config:
        from_attributes = True