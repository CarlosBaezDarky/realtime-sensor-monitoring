"""
Servidor principal del sistema de monitoreo en tiempo real
"""
import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import random

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text  # ✅ Agregar 'text' aquí
from sqlalchemy.orm import sessionmaker

# Importaciones absolutas
from websocket_manager import WebSocketManager
from config import Settings
from models import SensorData, Alert, Base

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
settings = Settings()

# Crear engine y tablas
engine = create_engine(settings.DATABASE_URL, echo=False)  # Cambiar a echo=False para menos ruido
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ CREAR TABLAS - Forma correcta para SQLAlchemy 2.0
def init_database():
    """Inicializar base de datos y crear tablas"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas de base de datos creadas correctamente")
        
        # Verificar tablas creadas
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.fetchall()
            logger.info(f"📊 Tablas en base de datos: {[t[0] for t in tables]}")
            
    except Exception as e:
        logger.error(f"❌ Error creando tablas: {e}")
        # Si falla, intentar recrear
        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Tablas recreadas después de error")
        except Exception as e2:
            logger.error(f"❌ Error grave: {e2}")
            raise

# Ejecutar inicialización
init_database()

# Componentes globales
ws_manager = WebSocketManager()

# Dependencia de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    logger.info("🚀 Iniciando sistema de monitoreo en tiempo real...")
    
    try:
        # Verificar que las tablas existen (usando text() de SQLAlchemy 2.0)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.fetchall()
            logger.info(f"✅ Tablas en base de datos: {[t[0] for t in tables]}")
        
        # Iniciar broadcast de datos
        asyncio.create_task(broadcast_sensor_data())
        logger.info("✅ Sistema de broadcast iniciado")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Error en startup: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("🛑 Deteniendo sistema de monitoreo...")

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Monitoreo en Tiempo Real",
    description="API para monitoreo de sensores ambientales con WebSockets",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos del frontend
try:
    app.mount("/static", StaticFiles(directory="../frontend"), name="static")
except:
    logger.warning("No se encontró directorio frontend para archivos estáticos")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """
    Servir el dashboard principal
    """
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sistema de Monitoreo</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center; }
            .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 25px; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .sensor-value { font-size: 48px; font-weight: bold; margin: 20px 0; }
            .alert { color: #e74c3c; animation: pulse 1s infinite; padding: 10px; border-left: 4px solid #e74c3c; background: #ffebee; margin: 10px 0; }
            .success { color: #27ae60; padding: 10px; border-left: 4px solid #27ae60; background: #e9f7ef; margin: 10px 0; }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
            button { padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #2980b9; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Sistema de Monitoreo en Tiempo Real</h1>
                <p id="connectionStatus">Conectando a WebSocket...</p>
            </div>
            <div class="grid">
                <div class="card">
                    <h2>📊 Datos de Sensores</h2>
                    <div id="sensors">
                        <div class="success">✅ Esperando datos del sistema...</div>
                    </div>
                    <button onclick="refreshData()">🔄 Actualizar</button>
                </div>
                <div class="card">
                    <h2>⚠️ Alertas</h2>
                    <div id="alerts">
                        <div class="success">✅ Sistema inicializado</div>
                    </div>
                    <button onclick="clearAlerts()">🗑️ Limpiar Alertas</button>
                </div>
            </div>
            <div class="card" style="margin-top: 25px;">
                <h2>📡 Información del Sistema</h2>
                <p><strong>WebSocket:</strong> <span id="wsStatus">Conectando...</span></p>
                <p><strong>Última actualización:</strong> <span id="lastUpdate">--:--:--</span></p>
                <p><strong>Datos recibidos:</strong> <span id="dataCount">0</span></p>
            </div>
        </div>
        <script>
            let ws = null;
            let dataCount = 0;
            
            function connectWebSocket() {
                ws = new WebSocket('ws://localhost:8000/ws/sensors');
                
                ws.onopen = () => {
                    console.log('✅ Conectado al WebSocket');
                    document.getElementById('connectionStatus').textContent = '✅ Conectado - Recibiendo datos en tiempo real';
                    document.getElementById('wsStatus').textContent = 'Conectado';
                    document.getElementById('wsStatus').style.color = '#27ae60';
                };
                
                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log('📡 Datos recibidos:', data);
                        dataCount++;
                        document.getElementById('dataCount').textContent = dataCount;
                        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                        
                        if (data.type === 'sensor_data') {
                            const sensor = data.data;
                            let html = `<div class="success">`;
                            html += `<p><strong>Sensor ID:</strong> ${sensor.sensor_id}</p>`;
                            if (sensor.temperature !== undefined) {
                                const tempClass = sensor.temperature > 35 ? 'alert' : '';
                                html += `<p><strong>Temperatura:</strong> <span class="sensor-value ${tempClass}">${sensor.temperature}°C</span></p>`;
                            }
                            if (sensor.humidity !== undefined) {
                                const humClass = sensor.humidity > 80 ? 'alert' : '';
                                html += `<p><strong>Humedad:</strong> <span class="sensor-value ${humClass}">${sensor.humidity}%</span></p>`;
                            }
                            if (sensor.pressure !== undefined) {
                                html += `<p><strong>Presión:</strong> <span class="sensor-value">${sensor.pressure}hPa</span></p>`;
                            }
                            html += `<p><small>Ubicación: ${sensor.location || 'Desconocida'}</small></p>`;
                            html += `<p><small>${new Date().toLocaleTimeString()}</small></p>`;
                            html += `</div>`;
                            document.getElementById('sensors').innerHTML = html;
                        }
                        
                        if (data.type === 'alert') {
                            const alerts = data.alerts;
                            let alertsHTML = '';
                            alerts.forEach(alert => {
                                alertsHTML += `<div class="alert">⚠️ ${alert.message}</div>`;
                            });
                            document.getElementById('alerts').innerHTML = alertsHTML;
                        }
                        
                    } catch (error) {
                        console.error('❌ Error procesando datos:', error);
                    }
                };
                
                ws.onclose = () => {
                    document.getElementById('connectionStatus').textContent = '❌ Desconectado - Reconectando en 3 segundos...';
                    document.getElementById('wsStatus').textContent = 'Desconectado';
                    document.getElementById('wsStatus').style.color = '#e74c3c';
                    setTimeout(connectWebSocket, 3000);
                };
                
                ws.onerror = (error) => {
                    console.error('❌ Error WebSocket:', error);
                };
            }
            
            function refreshData() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                    document.getElementById('sensors').innerHTML = '<div class="success">✅ Solicitando datos actualizados...</div>';
                }
            }
            
            function clearAlerts() {
                document.getElementById('alerts').innerHTML = '<div class="success">✅ Alertas limpiadas</div>';
            }
            
            // Conectar al iniciar
            connectWebSocket();
        </script>
    </body>
    </html>
    """)

@app.get("/api/health")
async def health_check():
    """
    Endpoint de salud del sistema
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": len(ws_manager.active_connections),
        "system": {
            "api_version": "1.0.0",
            "websocket_active": True,
            "database_connected": True
        }
    }

@app.get("/api/sensors")
async def get_sensors():
    """
    Obtener lista de sensores configurados
    """
    return {
        "sensors": [
            {"id": "sensor_001", "type": "temperature", "location": "Sala Principal"},
            {"id": "sensor_002", "type": "humidity", "location": "Sala Principal"},
            {"id": "sensor_003", "type": "pressure", "location": "Exterior"}
        ]
    }

@app.get("/api/history")
async def get_history(
    sensor_id: Optional[str] = None,
    hours: int = 24,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtener histórico de datos
    """
    try:
        from datetime import timedelta
        
        query = db.query(SensorData)
        if sensor_id:
            query = query.filter(SensorData.sensor_id == sensor_id)
        
        time_limit = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.filter(SensorData.timestamp >= time_limit)
        query = query.order_by(SensorData.timestamp.desc())
        query = query.limit(limit)
        
        results = query.all()
        
        return {
            "history": [
                {
                    "id": data.id,
                    "sensor_id": data.sensor_id,
                    "temperature": data.temperature,
                    "humidity": data.humidity,
                    "pressure": data.pressure,
                    "location": data.location,
                    "timestamp": data.timestamp.isoformat() if data.timestamp else None,
                    "device_type": data.device_type
                }
                for data in results
            ]
        }
    except Exception as e:
        logger.error(f"Error obteniendo histórico: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/api/alerts")
async def get_alerts(
    resolved: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Obtener alertas del sistema
    """
    query = db.query(Alert)
    
    if not resolved:
        query = query.filter(Alert.is_resolved == False)
    
    query = query.order_by(Alert.timestamp.desc())
    query = query.limit(limit)
    
    results = query.all()
    
    return {
        "alerts": [
            {
                "id": alert.id,
                "sensor_id": alert.sensor_id,
                "alert_type": alert.alert_type,
                "message": alert.message,
                "severity": alert.severity,
                "threshold_value": alert.threshold_value,
                "actual_value": alert.actual_value,
                "is_resolved": alert.is_resolved,
                "timestamp": alert.timestamp.isoformat() if alert.timestamp else None
            }
            for alert in results
        ]
    }

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Marcar alerta como reconocida
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"status": "acknowledged", "alert_id": alert_id}

@app.post("/api/sensor-data")
async def receive_sensor_data(data: dict, db: Session = Depends(get_db)):
    """
    Endpoint para recibir datos del sensor
    """
    try:
        # Guardar en base de datos
        sensor_data = SensorData(
            sensor_id=data.get("sensor_id"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            pressure=data.get("pressure"),
            location=data.get("location"),
            device_type=data.get("device_type")
        )
        
        db.add(sensor_data)
        db.commit()
        db.refresh(sensor_data)
        
        # Verificar alertas
        alerts = []
        if data.get("temperature") and data["temperature"] > settings.ALERT_THRESHOLD_TEMP:
            alert = Alert(
                sensor_id=data.get("sensor_id"),
                alert_type="high_temperature",
                message=f"Temperatura alta detectada: {data['temperature']}°C",
                severity="high",
                threshold_value=settings.ALERT_THRESHOLD_TEMP,
                actual_value=data["temperature"]
            )
            db.add(alert)
            alerts.append(alert)
        
        if data.get("humidity") and data["humidity"] > settings.ALERT_THRESHOLD_HUMIDITY:
            alert = Alert(
                sensor_id=data.get("sensor_id"),
                alert_type="high_humidity",
                message=f"Humedad alta detectada: {data['humidity']}%",
                severity="medium",
                threshold_value=settings.ALERT_THRESHOLD_HUMIDITY,
                actual_value=data["humidity"]
            )
            db.add(alert)
            alerts.append(alert)
        
        if alerts:
            db.commit()
            # Enviar alertas por WebSocket
            await ws_manager.broadcast_alerts([
                {
                    "id": a.id,
                    "sensor_id": a.sensor_id,
                    "alert_type": a.alert_type,
                    "message": a.message,
                    "severity": a.severity,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None
                }
                for a in alerts
            ])
        
        # Enviar datos por WebSocket
        await ws_manager.broadcast_sensor_data({
            **data,
            "id": sensor_data.id,
            "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None
        })
        
        return {
            "status": "success",
            "message": "Datos recibidos y procesados",
            "data_id": sensor_data.id
        }
    except Exception as e:
        logger.error(f"Error procesando datos de sensor: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """
    WebSocket para datos de sensores en tiempo real
    """
    await ws_manager.connect(websocket)
    
    try:
        # Enviar estado inicial
        await websocket.send_json({
            "type": "connection_established",
            "message": "Conectado al sistema de monitoreo",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Mantener conexión activa
        while True:
            # Recibir mensajes del cliente
            data = await websocket.receive_text()
            logger.debug(f"Mensaje recibido: {data}")
            
            # Procesar JSON si es válido
            try:
                json_data = json.loads(data)
                if json_data.get("type") == "subscribe":
                    sensor_id = json_data.get("sensor_id")
                    if sensor_id:
                        ws_manager.subscribe_sensor(websocket, sensor_id)
                        await websocket.send_json({
                            "type": "subscription_confirmed",
                            "sensor_id": sensor_id,
                            "message": f"Suscrito a sensor {sensor_id}"
                        })
            except json.JSONDecodeError:
                # No es JSON válido, ignorar
                pass
                    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("Cliente WebSocket desconectado")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        ws_manager.disconnect(websocket)

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket para alertas en tiempo real
    """
    await ws_manager.connect(websocket, channel="alerts")
    
    try:
        await websocket.send_json({
            "type": "alerts_channel",
            "message": "Conectado al canal de alertas",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

async def broadcast_sensor_data():
    """
    Tarea de background para broadcast de datos simulados
    """
    logger.info("📡 Iniciando simulación de datos de sensores...")
    
    while True:
        try:
            # Generar datos de sensores simulados
            sensor_types = ["temperature", "humidity", "pressure"]
            sensor_type = random.choice(sensor_types)
            
            if sensor_type == "temperature":
                value = round(random.uniform(15.0, 40.0), 2)
                unit = "°C"
            elif sensor_type == "humidity":
                value = round(random.uniform(30.0, 90.0), 2)
                unit = "%"
            else:
                value = round(random.uniform(950.0, 1050.0), 2)
                unit = "hPa"
            
            sensor_id = f"sensor_{random.randint(1, 5):03d}"
            location = random.choice(["Sala Principal", "Exterior", "Oficina", "Laboratorio"])
            
            sensor_data = {
                "sensor_id": sensor_id,
                sensor_type: value,
                "location": location,
                "device_type": sensor_type,
                "unit": unit,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Guardar en base de datos
            db = SessionLocal()
            try:
                # Crear objeto SensorData según el tipo de sensor
                record_data = {
                    "sensor_id": sensor_id,
                    "location": location,
                    "device_type": sensor_type
                }
                
                if sensor_type == "temperature":
                    record_data["temperature"] = value
                elif sensor_type == "humidity":
                    record_data["humidity"] = value
                else:
                    record_data["pressure"] = value
                
                sensor_record = SensorData(**record_data)
                db.add(sensor_record)
                db.commit()
                
                # Verificar alertas
                alerts = []
                if sensor_type == "temperature" and value > settings.ALERT_THRESHOLD_TEMP:
                    alert = Alert(
                        sensor_id=sensor_id,
                        alert_type="high_temperature",
                        message=f"¡ALERTA! Temperatura alta: {value}°C en {location}",
                        severity="high",
                        threshold_value=settings.ALERT_THRESHOLD_TEMP,
                        actual_value=value
                    )
                    db.add(alert)
                    alerts.append(alert)
                
                if sensor_type == "humidity" and value > settings.ALERT_THRESHOLD_HUMIDITY:
                    alert = Alert(
                        sensor_id=sensor_id,
                        alert_type="high_humidity",
                        message=f"¡ALERTA! Humedad alta: {value}% en {location}",
                        severity="medium",
                        threshold_value=settings.ALERT_THRESHOLD_HUMIDITY,
                        actual_value=value
                    )
                    db.add(alert)
                    alerts.append(alert)
                
                if alerts:
                    db.commit()
                    # Broadcast de alertas
                    await ws_manager.broadcast_alerts([
                        {
                            "id": a.id,
                            "sensor_id": a.sensor_id,
                            "alert_type": a.alert_type,
                            "message": a.message,
                            "severity": a.severity,
                            "timestamp": a.timestamp.isoformat() if a.timestamp else None
                        }
                        for a in alerts
                    ])
                
                # Broadcast de datos de sensores
                await ws_manager.broadcast_sensor_data(sensor_data)
                
                logger.debug(f"📝 Dato enviado: {sensor_id} = {value} {unit}")
                
            except Exception as e:
                logger.error(f"Error guardando dato: {e}")
                db.rollback()
            finally:
                db.close()
            
            # Esperar entre 2 y 5 segundos
            await asyncio.sleep(random.uniform(2, 5))
            
        except Exception as e:
            logger.error(f"Error en broadcast: {e}")
            await asyncio.sleep(5)

import uvicorn
import sys
import os

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("SISTEMA DE MONITOREO EN TIEMPO REAL")
    logger.info("=" * 50)
    logger.info("🌐 Dashboard: http://localhost:8000")
    logger.info("📡 WebSocket: ws://localhost:8000/ws/sensors")
    logger.info("🔌 API REST: http://localhost:8000/docs")
    logger.info("=" * 50)
    
    # ✅ Solución para Windows: sin reload o usando workers=1
    if sys.platform == "win32":
        # Windows no soporta bien reload con multiprocessing
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
    else:
        # Linux/Mac pueden usar reload
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)