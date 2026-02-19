/**
 * DASHBOARD.JS - Sistema de Monitoreo con SEMÁFOROS
 * Versión con datos dinámicos y alertas en tiempo real
 */

// ============================================
// CONFIGURACIÓN GLOBAL
// ============================================

const CONFIG = {
    MAX_RECONNECT_ATTEMPTS: 5,
    MAX_ALERTS: 50,
    MAX_DATA_POINTS: {
        '1min': 10,
        '5min': 30,
        '15min': 45,
        '1hour': 60
    },
    REFRESH_INTERVALS: {
        SEMAPHORES: 3000, // 3 segundos
        TOAST_TIMEOUT: 5000 // 5 segundos
    },
    THRESHOLDS: {
        TEMP_HIGH: 28,
        TEMP_CRITICAL: 32,
        TEMP_LOW: 18,
        HUMIDITY_HIGH: 75,
        HUMIDITY_CRITICAL: 85,
        CO2_HIGH: 900,
        CO2_CRITICAL: 1200,
        PRESSURE_LOW: 990,
        PRESSURE_HIGH: 1040
    },
    LOCATIONS: ['Sala Principal', 'Exterior', 'Laboratorio', 'Oficina', 'Almacén', 'Sótano', 'Azotea']
};

// ============================================
// ESTADO GLOBAL
// ============================================

const AppState = {
    ws: null,
    reconnectAttempts: 0,
    
    temperatureHistory: [],
    timestampHistory: [],
    previousValues: {
        temp: null,
        hum: null,
        pres: null,
        co2: null
    },
    
    activeAlerts: [],
    alertId: 0,
    currentFilter: 'all',
    chartPeriod: '1min',
    
    temperatureChart: null,
    
    elements: {}
};

// ============================================
// UTILIDADES
// ============================================

const Utils = {
    formatTime: (date = new Date()) => {
        return date.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },
    
    getRandomLocation: () => {
        return CONFIG.LOCATIONS[Math.floor(Math.random() * CONFIG.LOCATIONS.length)];
    },
    
    getSensorIcon: (sensorId) => {
        if (sensorId.includes('temp')) return '🌡️';
        if (sensorId.includes('hum')) return '💧';
        if (sensorId.includes('co2')) return '🏭';
        return '🌀';
    },
    
    getTempColor: (temp) => {
        if (temp > CONFIG.THRESHOLDS.TEMP_CRITICAL) return '#ef4444';
        if (temp > CONFIG.THRESHOLDS.TEMP_HIGH) return '#f59e0b';
        if (temp < CONFIG.THRESHOLDS.TEMP_LOW) return '#3b82f6';
        return '#10b981';
    },
    
    getCO2Color: (co2) => {
        if (co2 > CONFIG.THRESHOLDS.CO2_CRITICAL) return '#ef4444';
        if (co2 > CONFIG.THRESHOLDS.CO2_HIGH) return '#f59e0b';
        return '#10b981';
    },
    
    calculateTrend: (current, previous) => {
        if (previous === null) return { icon: '➡️', text: 'Estable' };
        if (current > previous) return { icon: '📈', text: 'Subiendo' };
        if (current < previous) return { icon: '📉', text: 'Bajando' };
        return { icon: '➡️', text: 'Estable' };
    }
};

// ============================================
// DOM HANDLER
// ============================================

const DOMHandler = {
    init: () => {
        AppState.elements = {
            statusLed: document.getElementById('statusLed'),
            statusText: document.getElementById('statusText'),
            lastUpdate: document.getElementById('lastUpdate'),
            activeAlertsCount: document.getElementById('activeAlertsCount'),
            connectionsCount: document.getElementById('connectionsCount'),
            
            tempValue: document.getElementById('tempValue'),
            humidityValue: document.getElementById('humidityValue'),
            pressureValue: document.getElementById('pressureValue'),
            co2Value: document.getElementById('co2Value'),
            
            tempTime: document.getElementById('tempTime'),
            humidityTime: document.getElementById('humidityTime'),
            pressureTime: document.getElementById('pressureTime'),
            co2Time: document.getElementById('co2Time'),
            
            tempTrend: document.getElementById('tempTrend'),
            humTrend: document.getElementById('humTrend'),
            presTrend: document.getElementById('presTrend'),
            co2Trend: document.getElementById('co2Trend'),
            
            tempLocation: document.getElementById('tempLocation'),
            humLocation: document.getElementById('humLocation'),
            presLocation: document.getElementById('presLocation'),
            co2Location: document.getElementById('co2Location'),
            
            tempAlertBadge: document.getElementById('tempAlertBadge'),
            humAlertBadge: document.getElementById('humAlertBadge'),
            presAlertBadge: document.getElementById('presAlertBadge'),
            co2AlertBadge: document.getElementById('co2AlertBadge'),
            
            criticalCount: document.getElementById('criticalCount'),
            statCritical: document.getElementById('statCritical'),
            statHigh: document.getElementById('statHigh'),
            statMedium: document.getElementById('statMedium'),
            statLow: document.getElementById('statLow'),
            alertsBadge: document.getElementById('alertsBadge'),
            
            semaphoreGrid: document.getElementById('semaphoreGrid'),
            alertsList: document.getElementById('alertsList'),
            toastContainer: document.getElementById('toastContainer'),
            temperatureChart: document.getElementById('temperatureChart')
        };
    },
    
    updateSensorValue: (sensor, value, unit, timestamp) => {
        const valueMap = {
            temp: 'tempValue',
            hum: 'humidityValue',
            pres: 'pressureValue',
            co2: 'co2Value'
        };
        
        const timeMap = {
            temp: 'tempTime',
            hum: 'humidityTime',
            pres: 'pressureTime',
            co2: 'co2Time'
        };
        
        const trendMap = {
            temp: 'tempTrend',
            hum: 'humTrend',
            pres: 'presTrend',
            co2: 'co2Trend'
        };
        
        const element = AppState.elements[valueMap[sensor]];
        const timeElement = AppState.elements[timeMap[sensor]];
        const trendElement = AppState.elements[trendMap[sensor]];
        
        if (element) {
            if (sensor === 'temp') {
                element.style.color = Utils.getTempColor(value);
            } else if (sensor === 'co2') {
                element.style.color = Utils.getCO2Color(value);
            }
            
            element.innerHTML = `${value}<span class="sensor-unit">${unit}</span>`;
        }
        
        if (timeElement) {
            timeElement.textContent = `Última actualización: ${timestamp}`;
        }
        
        const prev = AppState.previousValues[sensor];
        if (prev !== null && trendElement) {
            const trend = Utils.calculateTrend(value, prev);
            trendElement.innerHTML = `<span>${trend.icon} ${trend.text}</span>`;
        }
        
        AppState.previousValues[sensor] = value;
    },
    
    updateLocations: () => {
        if (AppState.elements.tempLocation) {
            AppState.elements.tempLocation.textContent = Utils.getRandomLocation();
            AppState.elements.humLocation.textContent = Utils.getRandomLocation();
            AppState.elements.presLocation.textContent = Utils.getRandomLocation();
            AppState.elements.co2Location.textContent = Utils.getRandomLocation();
        }
    },
    
    setSensorAlertBadge: (sensor, type, show) => {
        const badgeMap = {
            temp: 'tempAlertBadge',
            hum: 'humAlertBadge',
            pres: 'presAlertBadge',
            co2: 'co2AlertBadge'
        };
        
        const badge = AppState.elements[badgeMap[sensor]];
        if (badge) {
            if (show) {
                badge.style.display = 'block';
                badge.className = `alert-badge-sensor ${type === 'critical' ? 'critical' : 'warning'}`;
            } else {
                badge.style.display = 'none';
            }
        }
    }
};

// ============================================
// CHART MANAGER
// ============================================

const ChartManager = {
    init: () => {
        const ctx = AppState.elements.temperatureChart?.getContext('2d');
        if (!ctx) return;
        
        AppState.temperatureChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: AppState.timestampHistory,
                datasets: [{
                    label: 'Temperatura (°C)',
                    data: AppState.temperatureHistory,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#ef4444',
                    pointBorderColor: 'white',
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#1e293b',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        borderColor: '#334155',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: {
                        grid: { color: '#334155' },
                        ticks: { color: '#94a3b8' },
                        title: {
                            display: true,
                            text: 'Temperatura (°C)',
                            color: '#94a3b8'
                        }
                    },
                    x: {
                        grid: { color: '#334155' },
                        ticks: {
                            color: '#94a3b8',
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    },
    
    update: (temperature, timestamp) => {
        if (!AppState.temperatureChart) return;
        
        AppState.temperatureHistory.push(temperature);
        AppState.timestampHistory.push(timestamp);
        
        const maxPoints = CONFIG.MAX_DATA_POINTS[AppState.chartPeriod] || 10;
        
        if (AppState.temperatureHistory.length > maxPoints) {
            AppState.temperatureHistory.shift();
            AppState.timestampHistory.shift();
        }
        
        AppState.temperatureChart.data.datasets[0].data = AppState.temperatureHistory;
        AppState.temperatureChart.data.labels = AppState.timestampHistory;
        AppState.temperatureChart.update('none');
    },
    
    setPeriod: (period) => {
        AppState.chartPeriod = period;
        
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        AppState.temperatureHistory = [];
        AppState.timestampHistory = [];
    }
};

// ============================================
// WEBSOCKET MANAGER
// ============================================

const WebSocketManager = {
    connect: () => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/sensors`;
        
        AppState.ws = new WebSocket(wsUrl);
        
        AppState.ws.onopen = WebSocketManager.handleOpen;
        AppState.ws.onmessage = WebSocketManager.handleMessage;
        AppState.ws.onclose = WebSocketManager.handleClose;
        AppState.ws.onerror = WebSocketManager.handleError;
    },
    
    handleOpen: () => {
        console.log('✅ Conectado al servidor');
        AppState.elements.statusLed.className = 'status-led';
        AppState.elements.statusText.textContent = 'Conectado';
        AppState.elements.connectionsCount.textContent = '1';
        AppState.reconnectAttempts = 0;
        
        fetch('/api/current')
            .then(response => response.json())
            .then(data => DataHandler.updateFromSensor(data))
            .catch(console.error);
        
        SemaphoreManager.refresh();
    },
    
    handleMessage: (event) => {
        const data = JSON.parse(event.data);
        
        if (data.temperature !== undefined) {
            DataHandler.updateFromSensor(data);
        }
        
        if (data.type === 'alert' || (data.alerts && data.alerts.length > 0)) {
            const alerts = data.alerts || [data];
            AlertManager.processIncomingAlerts(alerts);
        }
        
        if (data.type === 'sensor_data') {
            DataHandler.updateFromSensor(data.data || data);
        }
    },
    
    handleClose: () => {
        console.log('❌ Conexión cerrada');
        AppState.elements.statusLed.className = 'status-led disconnected';
        AppState.elements.statusText.textContent = 'Desconectado';
        AppState.elements.connectionsCount.textContent = '0';
        
        if (AppState.reconnectAttempts < CONFIG.MAX_RECONNECT_ATTEMPTS) {
            AppState.reconnectAttempts++;
            setTimeout(WebSocketManager.connect, 2000 * AppState.reconnectAttempts);
        }
    },
    
    handleError: (error) => {
        console.error('❌ Error WebSocket:', error);
    }
};

// ============================================
// DATA HANDLER
// ============================================

const DataHandler = {
    updateFromSensor: (data) => {
        const now = Utils.formatTime();
        AppState.elements.lastUpdate.textContent = now;
        
        if (data.temperature !== undefined) {
            DOMHandler.updateSensorValue('temp', data.temperature, '°C', now);
        }
        if (data.humidity !== undefined) {
            DOMHandler.updateSensorValue('hum', data.humidity, '%', now);
        }
        if (data.pressure !== undefined) {
            DOMHandler.updateSensorValue('pres', data.pressure, 'hPa', now);
        }
        if (data.co2 !== undefined) {
            DOMHandler.updateSensorValue('co2', data.co2, 'ppm', now);
        }
        
        DOMHandler.updateLocations();
        
        if (data.temperature !== undefined) {
            ChartManager.update(data.temperature, now);
        }
        
        AlertManager.checkThresholds(data);
    }
};

// ============================================
// SEMAPHORE MANAGER
// ============================================

const SemaphoreManager = {
    refresh: () => {
        fetch('/api/semaphores/status')
            .then(response => response.json())
            .then(data => SemaphoreManager.updateDisplay(data.data))
            .catch(error => {
                console.error('Error obteniendo semáforos:', error);
                SemaphoreManager.showError();
            });
    },
    
    updateDisplay: (semaphoreData) => {
        const sensors = semaphoreData.sensors || {};
        const system = semaphoreData.system_semaphores || {};
        
        if (Object.keys(sensors).length === 0) {
            SemaphoreManager.showEmptyState(system);
            return;
        }
        
        let html = '';
        for (const [sensorId, stats] of Object.entries(sensors)) {
            const queuePercent = Math.min((stats.queue_size / 20) * 100, 100);
            const lastUpdate = stats.last_update ? new Date(stats.last_update).toLocaleTimeString() : 'Nunca';
            
            html += `
                <div class="semaphore-card">
                    <div class="semaphore-sensor">
                        <span>${Utils.getSensorIcon(sensorId)}</span>
                        ${sensorId}
                        <span style="margin-left: auto; font-size: 0.8rem; color: ${stats.state === 'idle' ? '#10b981' : '#f59e0b'}">
                            ${stats.state || 'IDLE'}
                        </span>
                    </div>
                    
                    <div class="semaphore-stats">
                        <div class="semaphore-stat">
                            <div class="stat-label">Lectores</div>
                            <div class="stat-value read-value">${stats.readers_count || 0}</div>
                        </div>
                        <div class="semaphore-stat">
                            <div class="stat-label">Escritores</div>
                            <div class="stat-value write-value">${stats.writers_waiting || 0}</div>
                        </div>
                        <div class="semaphore-stat">
                            <div class="stat-label">Sem Read</div>
                            <div class="stat-value queue-value">${stats.read_semaphore_value || 0}</div>
                        </div>
                        <div class="semaphore-stat">
                            <div class="stat-label">Sem Write</div>
                            <div class="stat-value waiting-value">${stats.write_semaphore_value || 0}</div>
                        </div>
                    </div>
                    
                    <div class="semaphore-queue">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="color: #94a3b8;">Cola de datos</span>
                            <span style="color: #10b981;">${stats.queue_size || 0} items</span>
                        </div>
                        <div class="queue-bar">
                            <div class="queue-fill" style="width: ${queuePercent}%;"></div>
                        </div>
                    </div>
                    
                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 10px; text-align: right;">
                        Última actividad: ${lastUpdate}
                    </div>
                </div>
            `;
        }
        
        // Agregar estadísticas del sistema
        html += `
            <div class="semaphore-card" style="background: linear-gradient(135deg, #2563eb, #7c3aed);">
                <div class="semaphore-sensor" style="color: white;">
                    <span>📊</span> Estadísticas del Sistema
                </div>
                <div class="semaphore-stats">
                    <div class="semaphore-stat" style="background: rgba(255,255,255,0.1);">
                        <div class="stat-label" style="color: rgba(255,255,255,0.8);">Alertas en cola</div>
                        <div class="stat-value" style="color: white;">${system.alert_queue_size || 0}</div>
                    </div>
                    <div class="semaphore-stat" style="background: rgba(255,255,255,0.1);">
                        <div class="stat-label" style="color: rgba(255,255,255,0.8);">Broadcast</div>
                        <div class="stat-value" style="color: white;">${system.broadcast_semaphore || 10}</div>
                    </div>
                </div>
                <div style="color: rgba(255,255,255,0.8); font-size: 0.8rem; margin-top: 10px;">
                    ⏱️ Uptime: ${semaphoreData.uptime_formatted || 'N/A'}
                </div>
            </div>
        `;
        
        AppState.elements.semaphoreGrid.innerHTML = html;
    },
    
    showEmptyState: (system) => {
        AppState.elements.semaphoreGrid.innerHTML = `
            <div class="semaphore-card">
                <div class="semaphore-sensor">
                    <span>ℹ️</span> No hay sensores activos
                </div>
                <div class="semaphore-stats">
                    <div class="semaphore-stat">
                        <div class="stat-label">Broadcast</div>
                        <div class="stat-value read-value">${system.broadcast_semaphore || 10}</div>
                    </div>
                    <div class="semaphore-stat">
                        <div class="stat-label">DB</div>
                        <div class="stat-value write-value">${system.db_semaphore || 3}</div>
                    </div>
                </div>
            </div>
        `;
    },
    
    showError: () => {
        AppState.elements.semaphoreGrid.innerHTML = `
            <div class="semaphore-card">
                <div class="semaphore-sensor">
                    <span>❌</span> Error cargando semáforos
                </div>
            </div>
        `;
    }
};

// ============================================
// ALERT MANAGER
// ============================================

const AlertManager = {
    checkThresholds: (data) => {
        const newAlerts = [];
        
        // Temperatura
        if (data.temperature > CONFIG.THRESHOLDS.TEMP_CRITICAL) {
            newAlerts.push(AlertManager.createAlert(
                'Temperatura', data.temperature, '°C',
                `🔥 Temperatura CRÍTICA: ${data.temperature}°C`,
                'critical', '🌡️'
            ));
            DOMHandler.setSensorAlertBadge('temp', 'critical', true);
        } else if (data.temperature > CONFIG.THRESHOLDS.TEMP_HIGH) {
            newAlerts.push(AlertManager.createAlert(
                'Temperatura', data.temperature, '°C',
                `⚠️ Temperatura alta: ${data.temperature}°C`,
                'high', '🌡️'
            ));
            DOMHandler.setSensorAlertBadge('temp', 'warning', true);
        } else if (data.temperature < CONFIG.THRESHOLDS.TEMP_LOW) {
            newAlerts.push(AlertManager.createAlert(
                'Temperatura', data.temperature, '°C',
                `❄️ Temperatura baja: ${data.temperature}°C`,
                'medium', '🌡️'
            ));
            DOMHandler.setSensorAlertBadge('temp', 'warning', true);
        } else {
            DOMHandler.setSensorAlertBadge('temp', null, false);
        }
        
        // Humedad
        if (data.humidity > CONFIG.THRESHOLDS.HUMIDITY_CRITICAL) {
            newAlerts.push(AlertManager.createAlert(
                'Humedad', data.humidity, '%',
                `💧 Humedad CRÍTICA: ${data.humidity}%`,
                'critical', '💧'
            ));
            DOMHandler.setSensorAlertBadge('hum', 'critical', true);
        } else if (data.humidity > CONFIG.THRESHOLDS.HUMIDITY_HIGH) {
            newAlerts.push(AlertManager.createAlert(
                'Humedad', data.humidity, '%',
                `⚠️ Humedad alta: ${data.humidity}%`,
                'high', '💧'
            ));
            DOMHandler.setSensorAlertBadge('hum', 'warning', true);
        } else {
            DOMHandler.setSensorAlertBadge('hum', null, false);
        }
        
        // CO2
        if (data.co2 > CONFIG.THRESHOLDS.CO2_CRITICAL) {
            newAlerts.push(AlertManager.createAlert(
                'CO₂', data.co2, 'ppm',
                `🏭 CO₂ CRÍTICO: ${data.co2} ppm`,
                'critical', '🏭'
            ));
            DOMHandler.setSensorAlertBadge('co2', 'critical', true);
        } else if (data.co2 > CONFIG.THRESHOLDS.CO2_HIGH) {
            newAlerts.push(AlertManager.createAlert(
                'CO₂', data.co2, 'ppm',
                `⚠️ CO₂ alto: ${data.co2} ppm`,
                'high', '🏭'
            ));
            DOMHandler.setSensorAlertBadge('co2', 'warning', true);
        } else {
            DOMHandler.setSensorAlertBadge('co2', null, false);
        }
        
        // Presión
        if (data.pressure < CONFIG.THRESHOLDS.PRESSURE_LOW || 
            data.pressure > CONFIG.THRESHOLDS.PRESSURE_HIGH) {
            newAlerts.push(AlertManager.createAlert(
                'Presión', data.pressure, 'hPa',
                `🌀 Presión anormal: ${data.pressure} hPa`,
                'low', '🌀'
            ));
            DOMHandler.setSensorAlertBadge('pres', 'warning', true);
        } else {
            DOMHandler.setSensorAlertBadge('pres', null, false);
        }
        
        newAlerts.forEach(alert => {
            AppState.activeAlerts.unshift(alert);
            ToastManager.show(alert);
        });
        
        if (AppState.activeAlerts.length > CONFIG.MAX_ALERTS) {
            AppState.activeAlerts = AppState.activeAlerts.slice(0, CONFIG.MAX_ALERTS);
        }
        
        AlertManager.updateList();
    },
    
    createAlert: (sensor, value, unit, message, severity, icon) => {
        return {
            id: AppState.alertId++,
            sensor: sensor,
            value: value,
            unit: unit,
            message: message,
            severity: severity,
            timestamp: new Date(),
            sensorIcon: icon,
            acknowledged: false
        };
    },
    
    processIncomingAlerts: (alerts) => {
        alerts.forEach(alert => {
            const newAlert = {
                id: AppState.alertId++,
                sensor: alert.sensor || alert.alert_type?.split('_')[1] || 'Sensor',
                value: alert.value || alert.actual_value || 0,
                message: alert.message,
                severity: alert.severity || 'medium',
                timestamp: new Date(alert.timestamp || Date.now()),
                sensorIcon: alert.sensor === 'Temperatura' ? '🌡️' : 
                           alert.sensor === 'Humedad' ? '💧' : 
                           alert.sensor === 'CO₂' ? '🏭' : '🌀',
                acknowledged: false
            };
            AppState.activeAlerts.unshift(newAlert);
            ToastManager.show(newAlert);
        });
        
        AlertManager.updateList();
    },
    
    updateList: () => {
        const filteredAlerts = AppState.currentFilter === 'all' 
            ? AppState.activeAlerts 
            : AppState.activeAlerts.filter(a => a.severity === AppState.currentFilter);
        
        if (filteredAlerts.length === 0) {
            AppState.elements.alertsList.innerHTML = `
                <div class="alert-item alert-low">
                    <div class="alert-header">
                        <div class="alert-title">
                            <div class="alert-icon">✅</div>
                            Sin alertas
                        </div>
                    </div>
                    <div class="alert-message">
                        No hay alertas activas en este momento
                    </div>
                </div>
            `;
        } else {
            AppState.elements.alertsList.innerHTML = filteredAlerts.map(alert => `
                <div class="alert-item alert-${alert.severity}" data-id="${alert.id}" data-severity="${alert.severity}">
                    <div class="alert-header">
                        <div class="alert-title">
                            <div class="alert-icon">${alert.sensorIcon}</div>
                            ${alert.sensor} - ${AlertManager.getSeverityLabel(alert.severity)}
                        </div>
                        <div class="alert-time">${moment(alert.timestamp).fromNow()}</div>
                    </div>
                    <div class="alert-message">
                        ${alert.message}
                    </div>
                    <div class="alert-footer">
                        <div class="alert-sensor">
                            <span>${alert.sensorIcon}</span> ${alert.sensor}
                        </div>
                        <div class="alert-actions">
                            ${!alert.acknowledged ? 
                                `<button class="alert-btn" onclick="AlertManager.acknowledge(${alert.id})">✓ Reconocer</button>` : 
                                '<span style="color: #10b981;">✓ Reconocida</span>'}
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        AlertManager.updateCounters();
    },
    
    getSeverityLabel: (severity) => {
        const labels = {
            'critical': '🔴 CRÍTICA',
            'high': '🟠 ALTA',
            'medium': '🟡 MEDIA',
            'low': '🔵 BAJA'
        };
        return labels[severity] || severity.toUpperCase();
    },
    
    updateCounters: () => {
        const critical = AppState.activeAlerts.filter(a => a.severity === 'critical').length;
        const high = AppState.activeAlerts.filter(a => a.severity === 'high').length;
        const medium = AppState.activeAlerts.filter(a => a.severity === 'medium').length;
        const low = AppState.activeAlerts.filter(a => a.severity === 'low').length;
        
        if (AppState.elements.criticalCount) AppState.elements.criticalCount.textContent = critical;
        if (AppState.elements.statCritical) AppState.elements.statCritical.textContent = critical;
        if (AppState.elements.statHigh) AppState.elements.statHigh.textContent = high;
        if (AppState.elements.statMedium) AppState.elements.statMedium.textContent = medium;
        if (AppState.elements.statLow) AppState.elements.statLow.textContent = low;
        
        if (AppState.elements.activeAlertsCount) {
            AppState.elements.activeAlertsCount.textContent = AppState.activeAlerts.length;
        }
        
        const badge = AppState.elements.alertsBadge;
        if (badge) {
            if (critical > 0) {
                badge.style.background = '#ef4444';
                badge.innerHTML = `<span>${critical}</span> críticas`;
            } else if (high > 0) {
                badge.style.background = '#f59e0b';
                badge.innerHTML = `<span>${high}</span> altas`;
            } else if (medium > 0) {
                badge.style.background = '#3b82f6';
                badge.innerHTML = `<span>${medium}</span> medias`;
            } else if (low > 0) {
                badge.style.background = '#10b981';
                badge.innerHTML = `<span>${low}</span> bajas`;
            } else {
                badge.style.background = '#64748b';
                badge.innerHTML = '0 alertas';
            }
        }
    },
    
    acknowledge: (alertId) => {
        const alert = AppState.activeAlerts.find(a => a.id == alertId);
        if (alert) {
            alert.acknowledged = true;
            AlertManager.updateList();
            
            ToastManager.show({
                severity: 'low',
                message: 'Alerta reconocida',
                sensor: 'Sistema'
            });
        }
    },
    
    filter: (severity) => {
        AppState.currentFilter = severity;
        
        document.querySelectorAll('.alert-filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        if (event) event.target.classList.add('active');
        
        AlertManager.updateList();
    },
    
    clearAll: () => {
        AppState.activeAlerts = [];
        AlertManager.updateList();
        
        ToastManager.show({
            severity: 'low',
            message: 'Todas las alertas han sido limpiadas',
            sensor: 'Sistema'
        });
    }
};

// ============================================
// TOAST MANAGER
// ============================================

const ToastManager = {
    show: (alert) => {
        const toast = document.createElement('div');
        toast.className = `toast ${alert.severity}`;
        
        const severityIcon = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵'
        }[alert.severity] || '⚪';
        
        toast.innerHTML = `
            <div class="toast-header">
                <span>${severityIcon} ${alert.severity.toUpperCase()}</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div>${alert.message}</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">
                ${moment().format('HH:mm:ss')}
            </div>
        `;
        
        AppState.elements.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, CONFIG.REFRESH_INTERVALS.TOAST_TIMEOUT);
    }
};

// ============================================
// EXPOSICIÓN GLOBAL DE FUNCIONES
// ============================================

window.setChartPeriod = (period) => ChartManager.setPeriod(period);
window.refreshSemaphores = () => SemaphoreManager.refresh();
window.filterAlerts = (severity) => AlertManager.filter(severity);
window.acknowledgeAlert = (alertId) => AlertManager.acknowledge(alertId);
window.clearAllAlerts = () => AlertManager.clearAll();

// ============================================
// INICIALIZACIÓN
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚦 Inicializando dashboard con semáforos...');
    
    DOMHandler.init();
    ChartManager.init();
    WebSocketManager.connect();
    
    setInterval(SemaphoreManager.refresh, CONFIG.REFRESH_INTERVALS.SEMAPHORES);
});