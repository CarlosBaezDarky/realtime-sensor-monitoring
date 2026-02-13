"""
Servidor principal del sistema de monitoreo en tiempo real
CON SEMÁFOROS PARA CONTROL DE CONCURRENCIA
"""
import asyncio
import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import random
import threading

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
from sensor_semaphore import sensor_semaphore_manager, SensorSemaphore

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
    pool_size=10,  # Pool de conexiones
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
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas recreadas después de error")

init_database()

# Dependencia de base de datos CON SEMÁFORO
def get_db():
    """Obtiene sesión de base de datos con control de semáforo"""
    db_acquired = sensor_semaphore_manager.acquire_db(timeout=5)
    if not db_acquired:
        logger.warning("⚠️ Semáforo de DB no disponible, usando conexión directa")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        if db_acquired:
            sensor_semaphore_manager.release_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación con semáforos"""
    logger.info("🚀 Iniciando sistema de monitoreo con SEMÁFOROS...")
    
    # Iniciar tareas de background
    broadcast_task = asyncio.create_task(broadcast_sensor_data())
    alert_processor_task = asyncio.create_task(process_alert_queue())
    
    logger.info(f"✅ Sistema de monitoreo iniciado - {settings.VERSION}")
    logger.info(f"🚦 Semáforos configurados: Readers={settings.MAX_CONCURRENT_READERS}")
    
    yield
    
    # Shutdown
    broadcast_task.cancel()
    alert_processor_task.cancel()
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

# Montar archivos estáticos
try:
    app.mount("/static", StaticFiles(directory="../frontend"), name="static")
except:
    logger.warning("No se encontró directorio frontend")

# ============= ENDPOINTS DE SEMÁFOROS =============

@app.get("/api/semaphores/status")
async def get_semaphore_status():
    """
    🚦 ENDPOINT PRINCIPAL: Estado de todos los semáforos del sistema
    """
    stats = sensor_semaphore_manager.get_system_stats()
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": stats
    }

@app.get("/api/semaphores/sensor/{sensor_id}")
async def get_sensor_semaphore_status(sensor_id: str):
    """
    🚦 Obtiene estado del semáforo para un sensor específico
    """
    sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
    return {
        "status": "success",
        "sensor_id": sensor_id,
        "data": sem.get_stats()
    }

@app.post("/api/semaphores/test/concurrency")
async def test_semaphore_concurrency(background_tasks: BackgroundTasks):
    """
    🚦 Prueba de concurrencia con semáforos
    """
    def concurrent_reader(reader_id: int, sensor_id: str):
        """Simula un lector concurrente"""
        sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
        
        if sem.acquire_read(timeout=2):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                logger.info(f"📖 Lector {reader_id} leyendo sensor {sensor_id}")
            finally:
                sem.release_read()
    
    def concurrent_writer(writer_id: int, sensor_id: str):
        """Simula un escritor concurrente"""
        sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
        
        if sem.acquire_write(timeout=2):
            try:
                time.sleep(random.uniform(0.2, 0.8))
                logger.info(f"✍️ Escritor {writer_id} escribiendo sensor {sensor_id}")
            finally:
                sem.release_write()
    
    # Iniciar pruebas
    sensor_id = "test_sensor_001"
    for i in range(5):
        background_tasks.add_task(concurrent_reader, i, sensor_id)
    for i in range(2):
        background_tasks.add_task(concurrent_writer, i, sensor_id)
    
    return {
        "message": "Prueba de concurrencia iniciada",
        "sensor_id": sensor_id,
        "readers": 5,
        "writers": 2
    }

# ============= ENDPOINTS PRINCIPALES =============

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Dashboard principal con soporte para semáforos"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sistema de Monitoreo con Semáforos</title>
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center; }}
            .grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 25px; }}
            .card {{ background: white; padding: 25px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .semaphore-card {{ background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; margin-top: 20px; }}
            .sensor-value {{ font-size: 48px; font-weight: bold; margin: 20px 0; }}
            .alert {{ color: #e74c3c; animation: pulse 1s infinite; padding: 10px; border-left: 4px solid #e74c3c; background: #ffebee; margin: 10px 0; }}
            .success {{ color: #27ae60; padding: 10px; border-left: 4px solid #27ae60; background: #e9f7ef; margin: 10px 0; }}
            .info {{ color: #3498db; padding: 10px; border-left: 4px solid #3498db; background: #e1f0fa; margin: 10px 0; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} 100% {{ opacity: 1; }} }}
            button {{ padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }}
            button:hover {{ background: #2980b9; }}
            .badge {{ display: inline-block; padding: 5px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
            .badge-red {{ background: #e74c3c; color: white; }}
            .badge-green {{ background: #27ae60; color: white; }}
            .badge-blue {{ background: #3498db; color: white; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚦 Sistema de Monitoreo con SEMÁFOROS</h1>
                <p id="connectionStatus">Conectando a WebSocket...</p>
                <div>
                    <span class="badge badge-blue" id="semaphoreStatus">Semáforos: Activos</span>
                    <span class="badge" id="readerCount">Lectores: 0</span>
                    <span class="badge" id="writerCount">Escritores: 0</span>
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h2>📊 Datos de Sensores</h2>
                    <div id="sensors">
                        <div class="success">✅ Esperando datos...</div>
                    </div>
                    <button onclick="refreshData()">🔄 Actualizar</button>
                    <button onclick="testConcurrency()">🧪 Probar Concurrencia</button>
                </div>
                
                <div class="card">
                    <h2>⚠️ Alertas</h2>
                    <div id="alerts">
                        <div class="success">✅ Sistema inicializado</div>
                    </div>
                    <button onclick="clearAlerts()">🗑️ Limpiar</button>
                </div>
            </div>
            
            <div class="card semaphore-card">
                <h2>🚦 Estado de Semáforos</h2>
                <div id="semaphoreInfo">
                    <p>Cargando estado de semáforos...</p>
                </div>
                <button onclick="refreshSemaphores()">🔄 Actualizar Semáforos</button>
            </div>
            
            <div class="card">
                <h2>📡 Información del Sistema</h2>
                <p><strong>WebSocket:</strong> <span id="wsStatus">Conectando...</span></p>
                <p><strong>Última actualización:</strong> <span id="lastUpdate">--:--:--</span></p>
                <p><strong>Datos recibidos:</strong> <span id="dataCount">0</span></p>
                <p><strong>Conexiones activas:</strong> <span id="activeConnections">0</span></p>
                <p><strong>Versión:</strong> {settings.VERSION}</p>
            </div>
        </div>
        
        <script>
            let ws = null;
            let dataCount = 0;
            
            function connectWebSocket() {{
                ws = new WebSocket('ws://localhost:8000/ws/sensors');
                
                ws.onopen = () => {{
                    console.log('✅ Conectado al WebSocket');
                    document.getElementById('connectionStatus').innerHTML = '✅ Conectado - Sistema con SEMÁFOROS activo';
                    document.getElementById('wsStatus').innerHTML = 'Conectado';
                    document.getElementById('wsStatus').style.color = '#27ae60';
                    
                    // Solicitar estado de semáforos
                    refreshSemaphores();
                }};
                
                ws.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        console.log('📡 Datos:', data);
                        dataCount++;
                        document.getElementById('dataCount').innerHTML = dataCount;
                        document.getElementById('lastUpdate').innerHTML = new Date().toLocaleTimeString();
                        
                        if (data.type === 'sensor_data') {{
                            const sensor = data.data;
                            let html = `<div class="success">`;
                            html += `<p><strong>Sensor ID:</strong> ${{sensor.sensor_id}}</p>`;
                            if (sensor.temperature !== undefined) {{
                                const tempClass = sensor.temperature > 35 ? 'alert' : '';
                                html += `<p><strong>Temperatura:</strong> <span class="sensor-value ${{tempClass}}">${{sensor.temperature}}°C</span></p>`;
                            }}
                            if (sensor.humidity !== undefined) {{
                                const humClass = sensor.humidity > 80 ? 'alert' : '';
                                html += `<p><strong>Humedad:</strong> <span class="sensor-value ${{humClass}}">${{sensor.humidity}}%</span></p>`;
                            }}
                            if (sensor.pressure !== undefined) {{
                                html += `<p><strong>Presión:</strong> <span class="sensor-value">${{sensor.pressure}}hPa</span></p>`;
                            }}
                            html += `<p><small>Ubicación: ${{sensor.location || 'Desconocida'}}</small></p>`;
                            html += `<p><small>${{new Date().toLocaleTimeString()}}</small></p>`;
                            html += `</div>`;
                            document.getElementById('sensors').innerHTML = html;
                        }}
                        
                        if (data.type === 'alert') {{
                            const alerts = data.alerts;
                            let alertsHTML = '';
                            alerts.forEach(alert => {{
                                alertsHTML += `<div class="alert">⚠️ ${{alert.message}}</div>`;
                            }});
                            document.getElementById('alerts').innerHTML = alertsHTML;
                        }}
                        
                    }} catch (error) {{
                        console.error('❌ Error:', error);
                    }}
                }};
                
                ws.onclose = () => {{
                    document.getElementById('connectionStatus').innerHTML = '❌ Desconectado - Reconectando...';
                    document.getElementById('wsStatus').innerHTML = 'Desconectado';
                    document.getElementById('wsStatus').style.color = '#e74c3c';
                    setTimeout(connectWebSocket, 3000);
                }};
            }}
            
            function refreshSemaphores() {{
                fetch('/api/semaphores/status')
                    .then(response => response.json())
                    .then(data => {{
                        let html = '';
                        const sensors = data.data.sensors;
                        const system = data.data.system_semaphores;
                        
                        html += '<h3>Sistema:</h3>';
                        html += `<p>Broadcast: ${{system.broadcast_semaphore}} | DB: ${{system.db_semaphore}} | Alertas: ${{system.alert_semaphore}}</p>`;
                        html += `<p>Cola de alertas: ${{system.alert_queue_size}} | Total sensores: ${{data.data.total_sensors}}</p>`;
                        
                        html += '<h3>Sensores Activos:</h3>';
                        for (const [sensor_id, stats] of Object.entries(sensors)) {{
                            html += `<div class="info">`;
                            html += `<strong>${{sensor_id}}</strong> - Estado: ${{stats.state}}<br>`;
                            html += `📖 Lectores: ${{stats.readers_count}} | ✍️ Escritores esperando: ${{stats.writers_waiting}}<br>`;
                            html += `🚦 Semáforo lectura: ${{stats.read_semaphore_value}} | Escritura: ${{stats.write_semaphore_value}}<br>`;
                            html += `📊 Cola: ${{stats.queue_size}} items`;
                            html += `</div>`;
                        }}
                        
                        document.getElementById('semaphoreInfo').innerHTML = html;
                        
                        // Actualizar badges
                        document.getElementById('readerCount').innerHTML = `Lectores: ${{Object.values(sensors).reduce((acc, s) => acc + s.readers_count, 0)}}`;
                        document.getElementById('writerCount').innerHTML = `Escritores: ${{Object.values(sensors).reduce((acc, s) => acc + s.writers_waiting, 0)}}`;
                    }});
            }}
            
            function testConcurrency() {{
                fetch('/api/semaphores/test/concurrency', {{ method: 'POST' }})
                    .then(response => response.json())
                    .then(data => {{
                        alert(`🧪 Prueba de concurrencia iniciada: ${{data.readers}} lectores, ${{data.writers}} escritores`);
                        setTimeout(refreshSemaphores, 2000);
                    }});
            }}
            
            function refreshData() {{
                if (ws && ws.readyState === WebSocket.OPEN) {{
                    ws.send(JSON.stringify({{ type: 'ping' }}));
                }}
                refreshSemaphores();
            }}
            
            function clearAlerts() {{
                document.getElementById('alerts').innerHTML = '<div class="success">✅ Alertas limpiadas</div>';
            }}
            
            // Conectar al iniciar
            connectWebSocket();
            
            // Actualizar semáforos cada 5 segundos
            setInterval(refreshSemaphores, 5000);
        </script>
    </body>
    </html>
    """)

@app.get("/api/health")
async def health_check():
    """Health check con información de semáforos"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": ws_manager.get_connection_count(),
        "semaphores": {
            "active": True,
            "sensors_monitored": len(sensor_semaphore_manager.sensor_semaphores),
            "system": sensor_semaphore_manager.get_system_stats()["system_semaphores"]
        }
    }

@app.get("/api/sensors")
async def get_sensors():
    """Lista de sensores disponibles"""
    return {
        "sensors": [
            {"id": "sensor_001", "type": "temperature", "location": "Sala Principal"},
            {"id": "sensor_002", "type": "humidity", "location": "Sala Principal"},
            {"id": "sensor_003", "type": "pressure", "location": "Exterior"},
            {"id": "sensor_004", "type": "temperature", "location": "Laboratorio"},
            {"id": "sensor_005", "type": "humidity", "location": "Oficina"}
        ]
    }

@app.get("/api/history")
async def get_history(
    sensor_id: Optional[str] = None,
    hours: int = 24,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Obtener histórico de datos con control de semáforos"""
    try:
        from datetime import timedelta
        
        # Adquirir semáforo de lectura del sensor
        if sensor_id:
            sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
            sem.acquire_read(timeout=3)
        
        try:
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
                        "device_type": data.device_type,
                        "processing_time": data.processing_time
                    }
                    for data in results
                ]
            }
        finally:
            if sensor_id:
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
    """
    Endpoint para recibir datos del sensor
    CON SEMÁFOROS para control de concurrencia
    """
    start_time = time.time()
    sensor_id = data.get("sensor_id")
    
    if not sensor_id:
        raise HTTPException(status_code=400, detail="sensor_id es requerido")
    
    # Obtener semáforo del sensor
    sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
    
    # Adquirir permiso de escritura (exclusivo)
    acquired = sem.acquire_write(timeout=5)
    if not acquired:
        logger.warning(f"⚠️ Sensor {sensor_id}: Timeout adquiriendo semáforo de escritura")
        # Encolar datos para procesamiento posterior
        sem.produce_data(data)
        return {
            "status": "queued",
            "message": "Datos encolados por alta concurrencia",
            "queue_size": len(sem.data_queue)
        }
    
    try:
        logger.info(f"✍️ Escribiendo datos de sensor {sensor_id}")
        
        # Guardar en base de datos
        sensor_data = SensorData(
            sensor_id=sensor_id,
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            pressure=data.get("pressure"),
            location=data.get("location"),
            device_type=data.get("device_type"),
            processing_time=time.time() - start_time,
            queue_wait_time=data.get("queue_wait_time")
        )
        
        db.add(sensor_data)
        db.commit()
        db.refresh(sensor_data)
        
        # Verificar alertas
        alerts = []
        
        if data.get("temperature") and data["temperature"] > settings.ALERT_THRESHOLD_TEMP:
            alert = Alert(
                sensor_id=sensor_id,
                alert_type="high_temperature",
                message=f"⚠️ Temperatura alta: {data['temperature']}°C",
                severity="high",
                threshold_value=settings.ALERT_THRESHOLD_TEMP,
                actual_value=data["temperature"]
            )
            db.add(alert)
            alerts.append(alert)
        
        if data.get("humidity") and data["humidity"] > settings.ALERT_THRESHOLD_HUMIDITY:
            alert = Alert(
                sensor_id=sensor_id,
                alert_type="high_humidity",
                message=f"⚠️ Humedad alta: {data['humidity']}%",
                severity="medium",
                threshold_value=settings.ALERT_THRESHOLD_HUMIDITY,
                actual_value=data["humidity"]
            )
            db.add(alert)
            alerts.append(alert)
        
        if alerts:
            db.commit()
            # Productor: encolar alertas
            for alert in alerts:
                sensor_semaphore_manager.produce_alert({
                    "id": alert.id,
                    "sensor_id": alert.sensor_id,
                    "alert_type": alert.alert_type,
                    "message": alert.message,
                    "severity": alert.severity,
                    "timestamp": alert.timestamp.isoformat() if alert.timestamp else None
                })
        
        # Productor: encolar datos para broadcast
        sem.produce_data({
            **data,
            "id": sensor_data.id,
            "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None
        })
        
        # Broadcast asíncrono
        background_tasks.add_task(
            ws_manager.broadcast_sensor_data,
            {
                **data,
                "id": sensor_data.id,
                "timestamp": sensor_data.timestamp.isoformat() if sensor_data.timestamp else None
            }
        )
        
        return {
            "status": "success",
            "message": "Datos recibidos y procesados",
            "data_id": sensor_data.id,
            "processing_time_ms": round((time.time() - start_time) * 1000, 2)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando datos de sensor {sensor_id}: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    finally:
        sem.release_write()

async def process_alert_queue():
    """
    Tarea de background: Consumidor de cola de alertas
    Procesa alertas usando semáforo productor-consumidor
    """
    logger.info("📢 Iniciando procesador de cola de alertas")
    
    while True:
        try:
            # Consumir alerta de la cola (espera con semáforo)
            alert_data = sensor_semaphore_manager.consume_alert(timeout=1)
            
            if alert_data:
                logger.info(f"📢 Procesando alerta: {alert_data.get('message')}")
                
                # Adquirir semáforo de broadcast para alertas
                acquired = sensor_semaphore_manager.acquire_broadcast(timeout=2)
                if acquired:
                    try:
                        await ws_manager.broadcast_alerts([alert_data])
                    finally:
                        sensor_semaphore_manager.release_broadcast()
            
            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            logger.info("Procesador de alertas detenido")
            break
        except Exception as e:
            logger.error(f"Error en procesador de alertas: {e}")
            await asyncio.sleep(1)

async def broadcast_sensor_data():
    """
    Tarea de background: Simulación de datos de sensores
    Con control de semáforos
    """
    logger.info("📡 Iniciando simulación de datos con SEMÁFOROS...")
    
    while True:
        try:
            # Generar datos simulados
            sensor_types = ["temperature", "humidity", "pressure"]
            sensor_type = random.choice(sensor_types)
            
            if sensor_type == "temperature":
                value = round(random.uniform(15.0, 45.0), 2)
                unit = "°C"
            elif sensor_type == "humidity":
                value = round(random.uniform(30.0, 95.0), 2)
                unit = "%"
            else:
                value = round(random.uniform(950.0, 1050.0), 2)
                unit = "hPa"
            
            sensor_id = f"sensor_{random.randint(1, 5):03d}"
            location = random.choice(["Sala Principal", "Exterior", "Oficina", "Laboratorio", "Almacén"])
            
            sensor_data = {
                "sensor_id": sensor_id,
                sensor_type: value,
                "location": location,
                "device_type": sensor_type,
                "unit": unit,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Enviar datos a través del endpoint interno
            async with asyncio.timeout(2):
                db = SessionLocal()
                try:
                    # Usar el mismo método que el endpoint
                    sensor_record = SensorData(
                        sensor_id=sensor_id,
                        **{sensor_type: value},
                        location=location,
                        device_type=sensor_type
                    )
                    
                    # Adquirir semáforo de DB
                    db_acquired = sensor_semaphore_manager.acquire_db(timeout=1)
                    
                    try:
                        db.add(sensor_record)
                        db.commit()
                        
                        # Broadcast
                        await ws_manager.broadcast_sensor_data(sensor_data)
                        
                    finally:
                        if db_acquired:
                            sensor_semaphore_manager.release_db()
                            
                except Exception as e:
                    logger.error(f"Error en simulación: {e}")
                    db.rollback()
                finally:
                    db.close()
            
            await asyncio.sleep(random.uniform(2, 4))
            
        except asyncio.CancelledError:
            logger.info("Simulación de datos detenida")
            break
        except Exception as e:
            logger.error(f"Error en broadcast: {e}")
            await asyncio.sleep(5)

# ============= WEBSOCKETS =============

@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """WebSocket con soporte de semáforos"""
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
                        
                        # Obtener estado del semáforo
                        sem = sensor_semaphore_manager.get_sensor_semaphore(sensor_id)
                        
                        await websocket.send_json({
                            "type": "subscription_confirmed",
                            "sensor_id": sensor_id,
                            "semaphore_status": sem.get_stats(),
                            "message": f"✅ Suscrito a sensor {sensor_id}"
                        })
                
                elif json_data.get("type") == "get_semaphore_stats":
                    # Enviar estadísticas de semáforos
                    await websocket.send_json({
                        "type": "semaphore_stats",
                        "data": sensor_semaphore_manager.get_system_stats(),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            except json.JSONDecodeError:
                # Respuesta a ping
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
    logger.info("=" * 60)
    
    if sys.platform == "win32":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)