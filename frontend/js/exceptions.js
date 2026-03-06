/**
 * exceptions.js - Panel de Excepciones
 * Sistema de Monitoreo de Sensores con Semáforos
 */
// Agregar al inicio del archivo para prevenir interferencia
(function() {
    // No interceptar clics en enlaces de navegación
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.tagName === 'A' || target.closest('a')) {
            // Dejar que el enlace haga su trabajo
            return true;
        }
    }, true);
})();

// ============================================
// CONFIGURACIÓN
// ============================================

const EXCEPTION_CONFIG = {
    WS_URL: 'ws://localhost:8000/ws/exceptions',
    REFRESH_INTERVAL: 5000,
    MAX_HISTORY: 100,
    ICONS: {
        'SensorConnectionError': '🔌',
        'SensorDataError': '📊',
        'SensorCalibrationError': '⚙️',
        'DatabaseError': '💾',
        'WebSocketError': '📡',
        'SemaphoreTimeoutError': '⏱️',
        'AlertQueueFullError': '⚠️'
    }
};

// ============================================
// ESTADO GLOBAL
// ============================================

const ExceptionState = {
    exceptions: [],
    currentTab: 'active',
    charts: {
        exceptionsChart: null,
        severityChart: null
    },
    elements: {},
    ws: null
};

// ============================================
// DOM HANDLER
// ============================================

const DOMHandler = {
    init: function() {
        ExceptionState.elements = {
            statusLed: document.getElementById('statusLed'),
            statusText: document.getElementById('statusText'),
            totalExceptions: document.getElementById('totalExceptions'),
            activeExceptions: document.getElementById('activeExceptions'),
            exceptionsList: document.getElementById('exceptionsList'),
            historyList: document.getElementById('historyList'),
            countersList: document.getElementById('countersList'),
            statCritical: document.getElementById('statCritical'),
            statHigh: document.getElementById('statHigh'),
            statMedium: document.getElementById('statMedium'),
            statLow: document.getElementById('statLow'),
            activeTab: document.getElementById('activeTab'),
            historyTab: document.getElementById('historyTab'),
            statsTab: document.getElementById('statsTab'),
            exceptionsChart: document.getElementById('exceptionsChart'),
            severityChart: document.getElementById('severityChart')
        };
    }
};

// ============================================
// WEBSOCKET MANAGER
// ============================================

const WebSocketManager = {
    connect: function() {
        ExceptionState.ws = new WebSocket(EXCEPTION_CONFIG.WS_URL);
        
        ExceptionState.ws.onopen = this.handleOpen;
        ExceptionState.ws.onmessage = this.handleMessage;
        ExceptionState.ws.onclose = this.handleClose;
        ExceptionState.ws.onerror = this.handleError;
    },
    
    handleOpen: function() {
        console.log('✅ Conectado al panel de excepciones');
        ExceptionState.elements.statusLed.className = 'status-led';
        ExceptionState.elements.statusText.textContent = 'Conectado';
    },
    
    handleMessage: function(event) {
        const data = JSON.parse(event.data);
        
        if (data.type === 'exception_update') {
            ExceptionManager.updateExceptions(data.exceptions);
            ExceptionManager.updateStats(data.stats);
        }
        
        if (data.type === 'new_exception') {
            NotificationManager.show(data.exception);
            ExceptionManager.refreshData();
        }
    },
    
    handleClose: function() {
        console.log('❌ Conexión cerrada');
        ExceptionState.elements.statusLed.className = 'status-led disconnected';
        ExceptionState.elements.statusText.textContent = 'Desconectado';
        
        // Intentar reconectar después de 3 segundos
        setTimeout(WebSocketManager.connect, 3000);
    },
    
    handleError: function(error) {
        console.error('❌ Error WebSocket:', error);
    }
};

// ============================================
// EXCEPTION MANAGER
// ============================================

const ExceptionManager = {
    /**
     * Simula una excepción aleatoria
     */
    simulate: function() {
        fetch('/api/exceptions/simulate', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.exception) {
                    NotificationManager.show(data.exception);
                }
                this.refreshData();
            })
            .catch(error => console.error('Error:', error));
    },
    
    /**
     * Refresca los datos desde la API
     */
    refreshData: function() {
        fetch('/api/exceptions')
            .then(response => response.json())
            .then(data => {
                ExceptionState.exceptions = data.exceptions || [];
                this.updateExceptions(ExceptionState.exceptions);
                this.updateStats(data.stats);
            })
            .catch(error => console.error('Error:', error));
    },
    
    /**
     * Actualiza las listas de excepciones
     */
    updateExceptions: function(exceptions) {
        const active = exceptions.filter(e => !e.resolved);
        const history = exceptions;
        
        // Actualizar contadores
        ExceptionState.elements.totalExceptions.textContent = exceptions.length;
        ExceptionState.elements.activeExceptions.textContent = active.length;
        
        // Renderizar activas
        if (active.length === 0) {
            ExceptionState.elements.exceptionsList.innerHTML = `
                <div class="exception-card low">
                    <div class="exception-header">
                        <div class="exception-type">
                            <div class="exception-icon">✅</div>
                            Sin excepciones activas
                        </div>
                    </div>
                    <div class="exception-message">
                        El sistema funciona correctamente
                    </div>
                </div>
            `;
        } else {
            ExceptionState.elements.exceptionsList.innerHTML = active
                .map(e => this.renderException(e))
                .join('');
        }
        
        // Renderizar historial
        if (history.length === 0) {
            ExceptionState.elements.historyList.innerHTML = `
                <div class="exception-card low">
                    <div class="exception-message">No hay historial de excepciones</div>
                </div>
            `;
        } else {
            ExceptionState.elements.historyList.innerHTML = history
                .map(e => this.renderException(e))
                .join('');
        }
    },
    
    /**
     * Renderiza una tarjeta de excepción
     */
    renderException: function(e) {
        const timeAgo = moment(e.timestamp).fromNow();
        const badgeClass = e.resolved ? 'badge-resolved' : 
                          e.severity === 'critical' ? 'badge-critical' :
                          e.severity === 'high' ? 'badge-high' :
                          e.severity === 'medium' ? 'badge-medium' : 'badge-low';
        
        return `
            <div class="exception-card ${e.severity}" data-id="${e.id}">
                <div class="exception-header">
                    <div class="exception-type">
                        <div class="exception-icon">${this.getIconForType(e.type)}</div>
                        ${e.type}
                        <span class="exception-badge ${badgeClass}">
                            ${e.resolved ? 'Resuelta' : e.severity.toUpperCase()}
                        </span>
                    </div>
                    <div class="exception-time">${timeAgo}</div>
                </div>
                
                <div class="exception-message">
                    ${e.message}
                </div>
                
                <div class="exception-details">
                    <div class="detail-row">
                        <span class="detail-label">Sensor:</span>
                        <span class="detail-value">${e.sensor_id || 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Severidad:</span>
                        <span class="detail-value">${e.severity}</span>
                    </div>
                    ${e.value ? `
                    <div class="detail-row">
                        <span class="detail-label">Valor:</span>
                        <span class="detail-value">${e.value}</span>
                    </div>
                    ` : ''}
                </div>
                
                <details>
                    <summary style="color: #94a3b8; cursor: pointer;">Ver traceback</summary>
                    <div class="traceback">
                        ${e.traceback || 'No disponible'}
                    </div>
                </details>
                
                <div class="exception-footer">
                    <div>
                        <span>ID: ${e.id}</span>
                    </div>
                    ${!e.resolved ? `
                    <button class="resolve-btn" onclick="ExceptionManager.resolve(${e.id})">
                        ✓ Marcar como resuelta
                    </button>
                    ` : `
                    <span style="color: #10b981;">
                        Resuelta ${moment(e.resolved_at).fromNow()}
                    </span>
                    `}
                </div>
            </div>
        `;
    },
    
    /**
     * Obtiene el icono para un tipo de excepción
     */
    getIconForType: function(type) {
        return EXCEPTION_CONFIG.ICONS[type] || '❓';
    },
    
    /**
     * Resuelve una excepción
     */
    resolve: function(id) {
        fetch(`/api/exceptions/${id}/resolve`, { method: 'POST' })
            .then(response => response.json())
            .then(() => this.refreshData())
            .catch(error => console.error('Error:', error));
    },
    
    /**
     * Actualiza las estadísticas
     */
    updateStats: function(stats) {
        if (!stats) return;
        
        ExceptionState.elements.statCritical.textContent = stats.by_severity.critical;
        ExceptionState.elements.statHigh.textContent = stats.by_severity.high;
        ExceptionState.elements.statMedium.textContent = stats.by_severity.medium;
        ExceptionState.elements.statLow.textContent = stats.by_severity.low;
        
        // Actualizar contadores
        const countersHtml = Object.entries(stats.counters)
            .map(([key, value]) => `
                <div class="detail-row">
                    <span class="detail-label">${key}:</span>
                    <span class="detail-value">${value}</span>
                </div>
            `).join('');
        
        if (ExceptionState.elements.countersList) {
            ExceptionState.elements.countersList.innerHTML = countersHtml;
        }
        
        // Actualizar gráficos
        ChartsManager.update(stats);
    },
    
    /**
     * Cambia de pestaña
     */
    switchTab: function(tab) {
        ExceptionState.currentTab = tab;
        
        // Actualizar tabs
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        event.target.classList.add('active');
        
        // Mostrar contenido correcto
        ExceptionState.elements.activeTab.style.display = tab === 'active' ? 'block' : 'none';
        ExceptionState.elements.historyTab.style.display = tab === 'history' ? 'block' : 'none';
        ExceptionState.elements.statsTab.style.display = tab === 'stats' ? 'block' : 'none';
    }
};

// ============================================
// CHARTS MANAGER
// ============================================

const ChartsManager = {
    /**
     * Inicializa los gráficos
     */
    init: function() {
        // Gráfico de tipos
        const ctx = ExceptionState.elements.exceptionsChart?.getContext('2d');
        if (ctx) {
            ExceptionState.charts.exceptionsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Excepciones por tipo',
                        data: [],
                        backgroundColor: '#ef4444',
                        borderColor: '#7f1d1d',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: { 
                            beginAtZero: true,
                            grid: { color: '#334155' },
                            ticks: { color: '#94a3b8' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8' }
                        }
                    }
                }
            });
        }
        
        // Gráfico de severidad
        const ctx2 = ExceptionState.elements.severityChart?.getContext('2d');
        if (ctx2) {
            ExceptionState.charts.severityChart = new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: ['Críticas', 'Altas', 'Medias', 'Bajas'],
                    datasets: [{
                        data: [0, 0, 0, 0],
                        backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#e2e8f0' }
                        }
                    }
                }
            });
        }
    },
    
    /**
     * Actualiza los gráficos
     */
    update: function(stats) {
        // Actualizar gráfico de tipos
        if (ExceptionState.charts.exceptionsChart && stats.counters) {
            ExceptionState.charts.exceptionsChart.data.labels = Object.keys(stats.counters);
            ExceptionState.charts.exceptionsChart.data.datasets[0].data = Object.values(stats.counters);
            ExceptionState.charts.exceptionsChart.update();
        }
        
        // Actualizar gráfico de severidad
        if (ExceptionState.charts.severityChart && stats.by_severity) {
            ExceptionState.charts.severityChart.data.datasets[0].data = [
                stats.by_severity.critical,
                stats.by_severity.high,
                stats.by_severity.medium,
                stats.by_severity.low
            ];
            ExceptionState.charts.severityChart.update();
        }
    }
};

// ============================================
// NOTIFICATION MANAGER
// ============================================

const NotificationManager = {
    /**
     * Muestra una notificación de nueva excepción
     */
    show: function(exception) {
        if (!exception) return;
        
        // Notificación desktop
        if (Notification.permission === 'granted') {
            new Notification('⚠️ Nueva Excepción', {
                body: exception.message,
                icon: '/static/icon.png',
                tag: 'exception-' + exception.id
            });
        }
        
        // Toast notification
        this.showToast(exception);
    },
    
    /**
     * Muestra un toast de notificación
     */
    showToast: function(exception) {
        const toast = document.createElement('div');
        toast.className = `toast ${exception.severity}`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        
        toast.innerHTML = `
            <div class="toast-header">
                <span>${this.getSeverityIcon(exception.severity)} ${exception.severity.toUpperCase()}</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div>${exception.message}</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">
                ${moment().format('HH:mm:ss')}
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto eliminar después de 5 segundos
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    },
    
    /**
     * Obtiene icono por severidad
     */
    getSeverityIcon: function(severity) {
        const icons = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵'
        };
        return icons[severity] || '⚪';
    }
};

// ============================================
// INICIALIZACIÓN
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚦 Inicializando panel de excepciones...');
    
    // Inicializar DOM
    DOMHandler.init();
    
    // Solicitar permisos de notificación
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Inicializar gráficos
    ChartsManager.init();
    
    // Conectar WebSocket
    WebSocketManager.connect();
    
    // Cargar datos iniciales
    ExceptionManager.refreshData();
    
    // Actualizar cada 5 segundos
    setInterval(() => ExceptionManager.refreshData(), EXCEPTION_CONFIG.REFRESH_INTERVAL);
});

// Exponer funciones globalmente
window.ExceptionManager = ExceptionManager;