"""
Servidor principal del sistema de monitoreo en tiempo real
CON SEMÁFOROS Y DATOS DINÁMICOS
"""
import asyncio
import logging
import json
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Importaciones con semáforos
from websocket_manager import ws_manager
from config import settings
from models import SensorData, Alert, Base
from sensor_semaphore import sensor_semaphore_manager

# Configuración de logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear engine y tablas
engine = create_engine(
    settings.DATABASE_URL, 
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_database():
    """Inicializar base de datos y crear tablas"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas de base de datos creadas correctamente")
    except Exception as e:
        logger.error(f"❌ Error creando tablas: {e}")

init_database()

# Dependencia de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación"""
    logger.info("🚀 Iniciando sistema de monitoreo con SEMÁFOROS...")
    
    # Iniciar tareas de background
    broadcast_task = asyncio.create_task(broadcast_sensor_data())
    alert_generator_task = asyncio.create_task(generate_alerts())
    
    logger.info(f"✅ Sistema de monitoreo iniciado - {settings.VERSION}")
    logger.info(f"🚦 Semáforos configurados: Readers={settings.MAX_CONCURRENT_READERS}")
    
    yield
    
    # Shutdown
    broadcast_task.cancel()
    alert_generator_task.cancel()
    logger.info("🛑 Sistema de monitoreo detenido")

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Monitoreo en Tiempo Real con Semáforos",
    description="API para monitoreo de sensores con control de concurrencia mediante semáforos",
    version=settings.VERSION,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= ARCHIVOS ESTÁTICOS =============

BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"✅ Archivos estáticos montados desde: {FRONTEND_DIR}")
else:
    logger.warning(f"⚠️ Directorio frontend no encontrado en: {FRONTEND_DIR}")

# ============= ENDPOINT PRINCIPAL =============

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Sirve el dashboard principal"""
    index_path = FRONTEND_DIR / "index.html"
    
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    
    return HTMLResponse("<h1>Error: index.html no encontrado</h1>")

# ============= ENDPOINTS DE SEMÁFOROS =============

@app.get("/api/semaphores/status")
async def get_semaphore_status():
    """Estado de todos los semáforos del sistema"""
    stats = sensor_semaphore_manager.get_system_stats()
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": stats
    }

@app.get("/api/semaphores/sensor/{sensor_id}")
async def get_sensor_semaphore_status(sensor_id: str):
    """Estado del semáforo para un sensor específico"""
    sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
    return {
        "status": "success",
        "sensor_id": sensor_id,
        "data": sem.get_stats()
    }

# ============= ENDPOINTS DE SENSORES =============

@app.get("/api/current")
async def get_current_data():
    """Datos actuales de todos los sensores"""
    # Simular lecturas de diferentes sensores
    return {
        "temperature": round(random.uniform(15.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 90.0), 2),
        "pressure": round(random.uniform(980.0, 1040.0), 2),
        "co2": random.randint(350, 1500),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/sensors")
async def get_sensors():
    """Lista de sensores disponibles"""
    sensors = []
    for i in range(1, 8):
        sensor_type = random.choice(["temperature", "humidity", "pressure", "co2"])
        locations = ["Sala Principal", "Exterior", "Oficina", "Laboratorio", "Almacén", "Sótano", "Azotea"]
        
        sensors.append({
            "id": f"sensor_{i:03d}",
            "type": sensor_type,
            "location": locations[i-1],
            "status": "active",
            "last_reading": datetime.now(timezone.utc).isoformat()
        })
    
    return {"sensors": sensors}

@app.get("/api/history/{sensor_id}")
async def get_sensor_history(
    sensor_id: str,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Histórico de un sensor específico"""
    try:
        time_limit = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Adquirir semáforo de lectura
        sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
        sem.acquire_read(timeout=3)
        
        try:
            query = db.query(SensorData).filter(
                SensorData.sensor_id == sensor_id,
                SensorData.timestamp >= time_limit
            ).order_by(SensorData.timestamp.desc()).limit(100)
            
            results = query.all()
            
            return {
                "sensor_id": sensor_id,
                "history": [
                    {
                        "timestamp": data.timestamp.isoformat(),
                        "value": getattr(data, data.device_type) if data.device_type else None,
                        "type": data.device_type
                    }
                    for data in results
                ]
            }
        finally:
            sem.release_read()
            
    except Exception as e:
        logger.error(f"Error obteniendo histórico: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/api/sensor-data")
async def receive_sensor_data(
    data: dict, 
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Recibir datos de sensor (POST)"""
    sensor_id = data.get("sensor_id")
    
    if not sensor_id:
        raise HTTPException(status_code=400, detail="sensor_id es requerido")
    
    sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
    
    # Adquirir semáforo de escritura
    acquired = sem.acquire_write(timeout=5)
    if not acquired:
        sem.produce_data(data)
        return {"status": "queued", "message": "Datos encolados"}
    
    try:
        sensor_data = SensorData(
            sensor_id=sensor_id,
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            pressure=data.get("pressure"),
            location=data.get("location"),
            device_type=data.get("device_type", "unknown")
        )
        
        db.add(sensor_data)
        db.commit()
        
        # Broadcast en tiempo real
        if background_tasks:
            background_tasks.add_task(
                ws_manager.broadcast_sensor_data,
                {
                    "sensor_id": sensor_id,
                    "type": "sensor_update",
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return {"status": "success", "data_id": sensor_data.id}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
    finally:
        sem.release_write()

# ============= TAREAS DE BACKGROUND =============

async def generate_alerts():
    """Generador automático de alertas basado en condiciones"""
    logger.info("⚠️ Iniciando generador automático de alertas...")
    
    alert_types = [
        {"type": "temperature", "message": "🔥 Temperatura CRÍTICA", "severity": "critical", "threshold": 32},
        {"type": "temperature", "message": "⚠️ Temperatura alta", "severity": "high", "threshold": 28},
        {"type": "temperature", "message": "❄️ Temperatura baja", "severity": "medium", "threshold": 18},
        {"type": "humidity", "message": "💧 Humedad CRÍTICA", "severity": "critical", "threshold": 85},
        {"type": "humidity", "message": "⚠️ Humedad alta", "severity": "high", "threshold": 75},
        {"type": "co2", "message": "🏭 CO₂ CRÍTICO", "severity": "critical", "threshold": 1200},
        {"type": "co2", "message": "⚠️ CO₂ alto", "severity": "high", "threshold": 900},
        {"type": "pressure", "message": "🌀 Presión anormal", "severity": "low", "threshold": None}
    ]
    
    while True:
        try:
            await asyncio.sleep(random.uniform(8, 15))  # Alertas cada 8-15 segundos
            
            # Seleccionar alerta aleatoria
            alert_info = random.choice(alert_types)
            
            # Generar valor según tipo
            if alert_info["type"] == "temperature":
                value = random.uniform(29, 38) if "CRÍTICA" in alert_info["message"] else random.uniform(25, 31)
            elif alert_info["type"] == "humidity":
                value = random.uniform(76, 92)
            elif alert_info["type"] == "co2":
                value = random.randint(950, 1500)
            else:
                value = random.uniform(950, 1060)
            
            sensor_id = f"sensor_{random.randint(1, 7):03d}"
            
            alert_data = {
                "id": random.randint(1000, 9999),
                "sensor": alert_info["type"].capitalize(),
                "sensor_id": sensor_id,
                "value": round(value, 2) if isinstance(value, float) else value,
                "unit": "°C" if alert_info["type"] == "temperature" else 
                        "%" if alert_info["type"] == "humidity" else
                        "ppm" if alert_info["type"] == "co2" else "hPa",
                "message": f"{alert_info['message']}: {round(value, 2) if isinstance(value, float) else value}",
                "severity": alert_info["severity"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "location": random.choice(["Sala Principal", "Exterior", "Laboratorio", "Oficina"])
            }
            
            # Producir alerta en la cola
            sensor_semaphore_manager.produce_alert(alert_data)
            
            # Broadcast inmediato
            await ws_manager.broadcast_alerts([alert_data])
            
            logger.info(f"📢 Alerta generada: {alert_data['message']}")
            
        except asyncio.CancelledError:
            logger.info("Generador de alertas detenido")
            break
        except Exception as e:
            logger.error(f"Error generando alerta: {e}")
            await asyncio.sleep(5)

async def broadcast_sensor_data():
    """Broadcast de datos de sensores simulados"""
    logger.info("📡 Iniciando simulación de datos en tiempo real...")
    
    while True:
        try:
            # Generar datos para múltiples sensores
            for i in range(1, 8):  # 7 sensores
                sensor_id = f"sensor_{i:03d}"
                sensor_type = random.choice(["temperature", "humidity", "pressure", "co2"])
                
                # Valores con tendencia realista
                if sensor_type == "temperature":
                    value = round(random.uniform(18.0, 34.0) + random.gauss(0, 1), 2)
                elif sensor_type == "humidity":
                    value = round(random.uniform(40.0, 85.0) + random.gauss(0, 2), 2)
                elif sensor_type == "pressure":
                    value = round(random.uniform(990.0, 1030.0) + random.gauss(0, 2), 2)
                else:  # co2
                    value = random.randint(380, 1300) + int(random.gauss(0, 20))
                    value = max(350, min(1500, value))
                
                location = ["Sala Principal", "Exterior", "Oficina", "Laboratorio", "Almacén", "Sótano", "Azotea"][i-1]
                
                sensor_data = {
                    "sensor_id": sensor_id,
                    sensor_type: value,
                    "location": location,
                    "device_type": sensor_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Actualizar semáforo del sensor (simular lecturas concurrentes)
                sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
                
                # Simular lectores/escritores aleatorios
                if random.random() < 0.3:  # 30% de probabilidad de simular actividad
                    if sem.acquire_read(timeout=0.1):
                        await asyncio.sleep(0.05)
                        sem.release_read()
                
                # Producir datos en la cola del sensor
                sem.produce_data(sensor_data)
                
                # Broadcast
                await ws_manager.broadcast_sensor_data(sensor_data)
            
            # También enviar datos combinados para el dashboard principal
            combined_data = {
                "temperature": round(random.uniform(18.0, 32.0), 2),
                "humidity": round(random.uniform(40.0, 80.0), 2),
                "pressure": round(random.uniform(1000.0, 1030.0), 2),
                "co2": random.randint(380, 1200),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await ws_manager.broadcast(combined_data)
            
            await asyncio.sleep(2)  # Actualizar cada 2 segundos
            
        except asyncio.CancelledError:
            logger.info("Simulación de datos detenida")
            break
        except Exception as e:
            logger.error(f"Error en broadcast: {e}")
            await asyncio.sleep(5)

# ============= WEBSOCKETS =============

@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """WebSocket principal para datos en tiempo real"""
    await ws_manager.connect(websocket)
    
    try:
        await websocket.send_json({
            "type": "connection_established",
            "message": "Conectado al sistema con SEMÁFOROS",
            "version": settings.VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            data = await websocket.receive_text()
            
            try:
                json_data = json.loads(data)
                
                if json_data.get("type") == "subscribe":
                    sensor_id = json_data.get("sensor_id")
                    if sensor_id:
                        ws_manager.subscribe_sensor(websocket, sensor_id)
                        sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
                        
                        await websocket.send_json({
                            "type": "subscription_confirmed",
                            "sensor_id": sensor_id,
                            "semaphore_status": sem.get_stats(),
                            "message": f"✅ Suscrito a sensor {sensor_id}"
                        })
                
                elif json_data.get("type") == "get_semaphore_stats":
                    await websocket.send_json({
                        "type": "semaphore_stats",
                        "data": sensor_semaphore_manager.get_system_stats(),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            except json.JSONDecodeError:
                if data == "ping":
                    await websocket.send_text("pong")
                    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        ws_manager.disconnect(websocket)

# ============= MAIN =============

import uvicorn
import sys

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚦 SISTEMA DE MONITOREO CON SEMÁFOROS")
    logger.info("=" * 60)
    logger.info(f"🌐 Dashboard: http://localhost:8000")
    logger.info(f"📡 WebSocket: ws://localhost:8000/ws/sensors")
    logger.info(f"🔌 API Docs: http://localhost:8000/docs")
    logger.info(f"🚦 Semáforos: http://localhost:8000/api/semaphores/status")
    logger.info(f"📁 Frontend: {FRONTEND_DIR}")
    logger.info("=" * 60)
    
    if sys.platform == "win32":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)