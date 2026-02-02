"""
Manejador de base de datos simplificado
"""
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from config import settings

# Crear engine y session
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependencia para obtener sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()