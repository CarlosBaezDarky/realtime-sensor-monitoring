/**
 * Sistema de Monitoreo en Tiempo Real - Frontend
 * app.js - Lógica principal del dashboard
 */

// Variables globales del sistema
class SensorDashboard {
    constructor() {
        this.ws = null;
        this.temperatureChart = null;
        this.autoUpdate = true;
        this.updateCount = 0;
        this.lastUpdateTime = null;
        this.chartData = {
            labels: [],
            temperatures: []
        };
        this.sensors = {};
        this.alertCount = 0;
        
        this.init();
    }
    
    // Inicializar el dashboard
    init() {
        console.log('🚀 Inicializando Dashboard de Monitoreo...');
        
        // Inicializar WebSocket
        this.initWebSocket();
        
        // Inicializar gráficos
        this.initChart();
        
        // Configurar event listeners
        this.setupEventListeners();
        
        // Inicializar hora del sistema
        this.initSystemTime();
        
        // Verificar estado inicial del sistema
        this.checkSystemStatus();
        
        console.log('✅ Dashboard inicializado correctamente');
    }
    
    // Inicializar conexión WebSocket
    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname || 'localhost';
        const port = window.location.port || '8000';
        const wsUrl = `${protocol}//${host}:${port}/ws/sensors`;
        
        console.log(`🔌 Conectando a WebSocket: ${wsUrl}`);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('✅ Conexión WebSocket establecida');
            this.updateConnectionStatus(true);
            this.updateApiStatus(true);
            this.addAlert('Sistema conectado correctamente', 'info');
            
            // Enviar suscripción inicial
            this.ws.send(JSON.stringify({
                type: 'subscribe',
                sensor_id: 'all',
                timestamp: new Date().toISOString()
            }));
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('❌ Error procesando mensaje WebSocket:', error);
                this.addAlert('Error procesando datos del servidor', 'high');
            }
        };
        
        this.ws.onclose = () => {
            console.log('❌ Conexión WebSocket cerrada');
            this.updateConnectionStatus(false);
            this.addAlert('Conexión perdida, reconectando...', 'high');
            
            // Intentar reconectar después de 5 segundos
            setTimeout(() => this.initWebSocket(), 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('❌ Error en conexión WebSocket:', error);
            this.updateConnectionStatus(false);
            this.addAlert('Error de conexión con el servidor', 'critical');
        };
    }
    
    // Manejar mensajes WebSocket
    handleWebSocketMessage(data) {
        this.updateCount++;
        const now = new Date();
        this.lastUpdateTime = now;
        
        // Actualizar tiempo de última actualización
        this.updateLastUpdateTime(now);
        
        // Calcular frecuencia de actualización
        this.updateDataRate();
        
        // Procesar según el tipo de mensaje
        switch(data.type) {
            case 'connection_established':
                console.log('📡 Conectado al sistema de monitoreo:', data.message);
                break;
                
            case 'sensor_data':
                this.handleSensorData(data.data);
                break;
                
            case 'alert':
                if (data.alerts && data.alerts.length > 0) {
                    data.alerts.forEach(alert => {
                        this.handleAlert(alert);
                    });
                }
                break;
                
            case 'subscription_confirmed':
                console.log('✅ Suscripción confirmada:', data.message);
                break;
                
            default:
                console.log('📨 Mensaje recibido:', data);
        }
    }
    
    // Manejar datos de sensores
    handleSensorData(sensorData) {
        if (!this.autoUpdate) return;
        
        const sensorId = sensorData.sensor_id || 'unknown';
        
        // Actualizar datos del sensor
        this.sensors[sensorId] = {
            ...sensorData,
            receivedAt: new Date().toISOString(),
            lastUpdate: new Date()
        };
        
        // Determinar tipo de sensor y actualizar UI
        if (sensorData.temperature !== undefined) {
            this.updateTemperatureSensor(sensorData);
        }
        
        if (sensorData.humidity !== undefined) {
            this.updateHumiditySensor(sensorData);
        }
        
        if (sensorData.pressure !== undefined) {
            this.updatePressureSensor(sensorData);
        }
        
        // Actualizar estadísticas
        this.updateStats();
    }
    
    // Manejar alertas
    handleAlert(alert) {
        const severity = alert.severity || 'medium';
        const message = alert.message || 'Nueva alerta del sistema';
        const sensorId = alert.sensor_id || 'Sistema';
        
        this.alertCount++;
        
        // Agregar alerta a la interfaz
        this.addAlert(`${sensorId}: ${message}`, severity);
        
        // Reproducir sonido de alerta si es crítica o alta
        if (severity === 'critical' || severity === 'high') {
            this.playAlertSound();
        }
        
        // Actualizar contador de alertas
        this.updateAlertCount();
    }
    
    // Actualizar sensor de temperatura
    updateTemperatureSensor(data) {
        const value = data.temperature;
        const sensorId = data.sensor_id || 'temp_001';
        
        // Crear o actualizar tarjeta de sensor
        let card = this.getSensorCard(sensorId);
        if (!card) {
            card = this.createSensorCard({
                id: sensorId,
                name: 'Sensor de Temperatura',
                type: 'temperature',
                value: value,
                unit: '°C',
                location: data.location || 'Desconocida'
            });
        }
        
        // Actualizar valores
        this.updateSensorCard(card, {
            value: value.toFixed(1),
            unit: '°C',
            time: new Date().toLocaleTimeString(),
            location: data.location || 'Desconocida'
        });
        
        // Actualizar gráfico
        this.updateTemperatureChart(value);
        
        // Verificar alertas
        if (value > 35) {
            card.classList.add('critical');
            if (value > 38) {
                this.addAlert(`¡Temperatura crítica en ${sensorId}: ${value.toFixed(1)}°C`, 'critical');
            }
        } else {
            card.classList.remove('critical');
        }
    }
    
    // Actualizar sensor de humedad
    updateHumiditySensor(data) {
        const value = data.humidity;
        const sensorId = data.sensor_id || 'hum_001';
        
        let card = this.getSensorCard(sensorId);
        if (!card) {
            card = this.createSensorCard({
                id: sensorId,
                name: 'Sensor de Humedad',
                type: 'humidity',
                value: value,
                unit: '%',
                location: data.location || 'Desconocida'
            });
        }
        
        this.updateSensorCard(card, {
            value: value.toFixed(1),
            unit: '%',
            time: new Date().toLocaleTimeString(),
            location: data.location || 'Desconocida'
        });
        
        // Verificar alertas
        if (value > 80) {
            card.classList.add('critical');
            this.addAlert(`¡Humedad alta en ${sensorId}: ${value.toFixed(1)}%`, 'high');
        } else if (value < 30) {
            card.classList.add('critical');
            this.addAlert(`¡Humedad baja en ${sensorId}: ${value.toFixed(1)}%`, 'high');
        } else {
            card.classList.remove('critical');
        }
    }
    
    // Actualizar sensor de presión
    updatePressureSensor(data) {
        const value = data.pressure;
        const sensorId = data.sensor_id || 'press_001';
        
        let card = this.getSensorCard(sensorId);
        if (!card) {
            card = this.createSensorCard({
                id: sensorId,
                name: 'Sensor de Presión',
                type: 'pressure',
                value: value,
                unit: 'hPa',
                location: data.location || 'Desconocida'
            });
        }
        
        this.updateSensorCard(card, {
            value: value.toFixed(1),
            unit: 'hPa',
            time: new Date().toLocaleTimeString(),
            location: data.location || 'Desconocida'
        });
    }
    
    // Obtener tarjeta de sensor existente
    getSensorCard(sensorId) {
        return document.querySelector(`[data-sensor-id="${sensorId}"]`);
    }
    
    // Crear nueva tarjeta de sensor
    createSensorCard(sensor) {
        const sensorGrid = document.getElementById('sensorGrid');
        
        const card = document.createElement('div');
        card.className = 'sensor-card';
        card.dataset.sensorId = sensor.id;
        
        const icon = this.getSensorIcon(sensor.type);
        
        card.innerHTML = `
            <div class="sensor-header">
                <div class="sensor-name">${icon} ${sensor.name}</div>
                <span class="sensor-type">${sensor.type}</span>
            </div>
            <div class="sensor-value ${this.getValueClass(sensor.type, sensor.value)}">
                ${sensor.value.toFixed(1)} ${sensor.unit}
            </div>
            <div class="sensor-meta">
                <div class="meta-item">
                    <span class="meta-label">📍 Ubicación</span>
                    <span class="meta-value sensor-location">${sensor.location}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">⏱️ Última lectura</span>
                    <span class="meta-value sensor-time">${new Date().toLocaleTimeString()}</span>
                </div>
            </div>
        `;
        
        sensorGrid.appendChild(card);
        return card;
    }
    
    // Actualizar tarjeta de sensor
    updateSensorCard(card, data) {
        const valueElement = card.querySelector('.sensor-value');
        const timeElement = card.querySelector('.sensor-time');
        const locationElement = card.querySelector('.sensor-location');
        
        if (valueElement) {
            valueElement.textContent = `${data.value} ${data.unit}`;
            // Actualizar clase de color si es temperatura
            if (valueElement.textContent.includes('°C')) {
                const tempValue = parseFloat(data.value);
                valueElement.className = 'sensor-value ' + this.getTemperatureClass(tempValue);
            }
        }
        
        if (timeElement) {
            timeElement.textContent = data.time;
        }
        
        if (locationElement) {
            locationElement.textContent = data.location;
        }
    }
    
    // Obtener icono según tipo de sensor
    getSensorIcon(type) {
        const icons = {
            'temperature': '<i class="fas fa-thermometer-half"></i>',
            'humidity': '<i class="fas fa-tint"></i>',
            'pressure': '<i class="fas fa-tachometer-alt"></i>',
            'default': '<i class="fas fa-microchip"></i>'
        };
        return icons[type] || icons.default;
    }
    
    // Obtener clase de color para temperatura
    getTemperatureClass(value) {
        if (value > 35) return 'temp-high';
        if (value < 18) return 'temp-low';
        return 'temp-normal';
    }
    
    // Obtener clase de color para valor
    getValueClass(type, value) {
        if (type === 'temperature') {
            return this.getTemperatureClass(value);
        }
        return '';
    }
    
    // Agregar alerta a la interfaz
    addAlert(message, severity = 'medium') {
        const alertsList = document.getElementById('alertsList');
        
        // Si es la alerta de inicialización, eliminarla
        const initialAlert = alertsList.querySelector('.alert-item.info');
        if (initialAlert && initialAlert.textContent.includes('Esperando datos')) {
            initialAlert.remove();
        }
        
        const alertItem = document.createElement('div');
        alertItem.className = `alert-item ${severity}`;
        
        const iconClass = this.getAlertIconClass(severity);
        const icon = this.getAlertIcon(severity);
        
        alertItem.innerHTML = `
            <div class="alert-icon ${severity}">${icon}</div>
            <div class="alert-content">
                <div class="alert-message">${message}</div>
                <div class="alert-time">
                    <i class="far fa-clock"></i> ${new Date().toLocaleTimeString()}
                </div>
            </div>
        `;
        
        // Agregar al inicio de la lista
        alertsList.insertBefore(alertItem, alertsList.firstChild);
        
        // Limitar a 15 alertas
        if (alertsList.children.length > 15) {
            alertsList.removeChild(alertsList.lastChild);
        }
        
        // Animar entrada
        alertItem.style.animation = 'slideIn 0.3s ease';
    }
    
    // Obtener icono de alerta
    getAlertIcon(severity) {
        const icons = {
            'critical': '<i class="fas fa-fire"></i>',
            'high': '<i class="fas fa-exclamation-triangle"></i>',
            'medium': '<i class="fas fa-exclamation-circle"></i>',
            'low': '<i class="fas fa-info-circle"></i>',
            'info': '<i class="fas fa-info-circle"></i>'
        };
        return icons[severity] || icons.info;
    }
    
    getAlertIconClass(severity) {
        return severity;
    }
    
    // Actualizar contador de alertas
    updateAlertCount() {
        const alertsList = document.getElementById('alertsList');
        const criticalAlerts = Array.from(alertsList.children).filter(
            alert => alert.classList.contains('critical') || alert.classList.contains('high')
        ).length;
        
        document.getElementById('activeAlerts').textContent = criticalAlerts;
    }
    
    // Inicializar gráfico de temperatura
    initChart() {
        const ctx = document.getElementById('temperatureChart').getContext('2d');
        
        this.temperatureChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.chartData.labels,
                datasets: [{
                    label: 'Temperatura (°C)',
                    data: this.chartData.temperatures,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#e74c3c',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return `Temperatura: ${context.parsed.y}°C`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Temperatura (°C)',
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Tiempo',
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            maxTicksLimit: 8
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                }
            }
        });
    }
    
    // Actualizar gráfico de temperatura
    updateTemperatureChart(temperature) {
        const now = new Date();
        const timeLabel = now.getHours().toString().padStart(2, '0') + ':' + 
                         now.getMinutes().toString().padStart(2, '0');
        
        // Agregar nuevos datos
        this.chartData.labels.push(timeLabel);
        this.chartData.temperatures.push(temperature);
        
        // Mantener solo últimos 20 puntos
        if (this.chartData.labels.length > 20) {
            this.chartData.labels.shift();
            this.chartData.temperatures.shift();
        }
        
        // Actualizar gráfico
        if (this.temperatureChart) {
            this.temperatureChart.update();
        }
    }
    
    // Actualizar estado de conexión
    updateConnectionStatus(connected) {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        const icon = document.getElementById('wsStatusIcon');
        const status = document.getElementById('wsStatus');
        
        if (connected) {
            dot.className = 'status-dot connected';
            text.textContent = 'Conectado';
            if (icon) icon.innerHTML = '<i class="fas fa-plug"></i>';
            if (status) status.textContent = 'Conectado';
        } else {
            dot.className = 'status-dot disconnected';
            text.textContent = 'Desconectado';
            if (icon) icon.innerHTML = '<i class="fas fa-plug"></i>';
            if (status) status.textContent = 'Desconectado';
        }
    }
    
    // Actualizar estado de API
    updateApiStatus(connected) {
        const icon = document.getElementById('apiStatusIcon');
        const status = document.getElementById('apiStatus');
        
        if (connected) {
            if (icon) icon.innerHTML = '<i class="fas fa-server"></i>';
            if (status) status.textContent = 'Activo';
        } else {
            if (icon) icon.innerHTML = '<i class="fas fa-server"></i>';
            if (status) status.textContent = 'Inactivo';
        }
    }
    
    // Actualizar frecuencia de datos
    updateDataRate() {
        if (this.updateCount > 0 && this.lastUpdateTime) {
            const now = Date.now();
            const diff = (now - this.lastUpdateTime.getTime()) / 1000;
            
            if (diff > 0) {
                const rate = (1 / diff).toFixed(1);
                document.getElementById('updateRate').textContent = rate;
                document.getElementById('dataRate').textContent = `${rate} Hz`;
            }
        }
    }
    
    // Actualizar tiempo de última actualización
    updateLastUpdateTime(time) {
        const lastUpdate = document.getElementById('lastUpdate');
        if (lastUpdate) {
            lastUpdate.innerHTML = `<i class="fas fa-sync-alt"></i> Última actualización: ${time.toLocaleTimeString()}`;
        }
    }
    
    // Inicializar hora del sistema
    initSystemTime() {
        setInterval(() => {
            const now = new Date();
            const timeDisplay = document.getElementById('timeDisplay');
            if (timeDisplay) {
                timeDisplay.textContent = 
                    now.getHours().toString().padStart(2, '0') + ':' + 
                    now.getMinutes().toString().padStart(2, '0') + ':' + 
                    now.getSeconds().toString().padStart(2, '0');
            }
        }, 1000);
    }
    
    // Actualizar estadísticas
    updateStats() {
        const sensorCount = Object.keys(this.sensors).length;
        document.getElementById('totalSensors').textContent = sensorCount;
    }
    
    // Reproducir sonido de alerta
    playAlertSound() {
        try {
            const alertSound = document.getElementById('alertSound');
            if (alertSound) {
                alertSound.currentTime = 0;
                alertSound.play().catch(e => {
                    console.log('No se pudo reproducir sonido de alerta:', e);
                });
            }
        } catch (e) {
            console.log('Error reproduciendo sonido de alerta');
        }
    }
    
    // Configurar event listeners
    setupEventListeners() {
        // Botón de pausar/reanudar
        const toggleBtn = document.getElementById('toggleUpdateBtn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleAutoUpdate());
        }
        
        // Botón de limpiar alertas
        const clearBtn = document.getElementById('clearAlertsBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearAlerts());
        }
        
        // Botón de exportar datos
        const exportBtn = document.getElementById('exportDataBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }
        
        // Botón de actualizar
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshDashboard());
        }
        
        // Selector de rango de tiempo
        const timeRange = document.getElementById('timeRange');
        if (timeRange) {
            timeRange.addEventListener('change', (e) => this.changeTimeRange(e.target.value));
        }
    }
    
    // Alternar actualización automática
    toggleAutoUpdate() {
        this.autoUpdate = !this.autoUpdate;
        const button = document.getElementById('toggleUpdateBtn');
        const icon = button.querySelector('i');
        
        if (this.autoUpdate) {
            button.innerHTML = '<i class="fas fa-pause"></i> Pausar';
            button.title = 'Pausar actualización automática';
            this.addAlert('Actualización automática reanudada', 'low');
        } else {
            button.innerHTML = '<i class="fas fa-play"></i> Reanudar';
            button.title = 'Reanudar actualización automática';
            this.addAlert('Actualización automática pausada', 'low');
        }
    }
    
    // Limpiar alertas
    clearAlerts() {
        if (confirm('¿Estás seguro de que quieres limpiar todas las alertas?')) {
            const alertsList = document.getElementById('alertsList');
            alertsList.innerHTML = `
                <div class="alert-item info">
                    <div class="alert-icon info"><i class="fas fa-info-circle"></i></div>
                    <div class="alert-content">
                        <div class="alert-message">No hay alertas activas</div>
                        <div class="alert-time">
                            <i class="far fa-clock"></i> ${new Date().toLocaleTimeString()}
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('activeAlerts').textContent = '0';
            this.addAlert('Alertas limpiadas correctamente', 'info');
        }
    }
    
    // Exportar datos
    exportData() {
        const exportData = {
            exportDate: new Date().toISOString(),
            systemInfo: {
                sensors: Object.keys(this.sensors).length,
                alerts: this.alertCount,
                updateRate: document.getElementById('dataRate').textContent,
                connectionStatus: document.getElementById('wsStatus').textContent
            },
            sensors: this.sensors,
            chartData: this.chartData,
            alerts: Array.from(document.querySelectorAll('.alert-item')).map(item => ({
                message: item.querySelector('.alert-message').textContent,
                time: item.querySelector('.alert-time').textContent.replace('⏱️ ', ''),
                severity: item.className.match(/critical|high|medium|low|info/)?.[0] || 'unknown'
            }))
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `monitoreo-export-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.addAlert('Datos exportados correctamente', 'info');
    }
    
    // Refrescar dashboard
    refreshDashboard() {
        location.reload();
    }
    
    // Cambiar rango de tiempo del gráfico
    changeTimeRange(range) {
        // Por ahora solo muestra un mensaje, podrías implementar lógica para cambiar el rango
        this.addAlert(`Rango de tiempo cambiado a ${range} minutos`, 'info');
    }
    
    // Verificar estado del sistema
    checkSystemStatus() {
        // Verificar conexión cada 30 segundos
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ 
                    type: 'ping', 
                    timestamp: new Date().toISOString() 
                }));
            }
        }, 30000);
        
        // Verificar estado de la API
        fetch('/api/health')
            .then(response => response.json())
            .then(data => {
                console.log('Estado del sistema:', data);
                this.updateApiStatus(data.status === 'healthy');
            })
            .catch(error => {
                console.error('Error verificando estado del sistema:', error);
                this.updateApiStatus(false);
                this.addAlert('No se pudo verificar el estado del sistema', 'high');
            });
    }
}

// Inicializar el dashboard cuando se cargue la página
document.addEventListener('DOMContentLoaded', () => {
    window.sensorDashboard = new SensorDashboard();
});