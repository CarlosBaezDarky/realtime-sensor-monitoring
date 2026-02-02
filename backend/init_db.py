"""
Script para inicializar la base de datos
"""
import sys
import os

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from models import Base
from config import settings

def init_database():
    """Inicializar base de datos y crear tablas"""
    print("🔧 Inicializando base de datos...")
    
    # Crear engine
    engine = create_engine(settings.DATABASE_URL, echo=True)
    
    try:
        # Eliminar tablas existentes (cuidado en producción)
        print("🗑️  Eliminando tablas existentes...")
        Base.metadata.drop_all(bind=engine)
        
        # Crear nuevas tablas
        print("📦 Creando tablas...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ Base de datos inicializada correctamente")
        
        # Verificar tablas creadas
        with engine.connect() as conn:
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = result.fetchall()
            print("📊 Tablas creadas:")
            for table in tables:
                print(f"   - {table[0]}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()