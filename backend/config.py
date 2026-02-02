from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Configuración de la base de datos
    DATABASE_URL: str = "sqlite:///./sensor_data.db"
    
    # Configuración de la API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Sistema de Monitoreo de Sensores"
    VERSION: str = "1.0.0"
    
    # Configuración de seguridad (si aplica)
    SECRET_KEY: str = "tu_clave_secreta_aqui_cambiar_en_produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Configuración de alertas
    ALERT_THRESHOLD_TEMP: float = 35.0
    ALERT_THRESHOLD_HUMIDITY: float = 80.0
    
    # Configuración de logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Instancia global de configuración
settings = Settings()