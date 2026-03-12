/**
 * recursive.js - Dashboard de Análisis Recursivo
 * Sistema de Monitoreo de Sensores con Semáforos
 * 
 * Implementa algoritmos recursivos para detección de patrones
 */

// ============================================
// CONFIGURACIÓN
// ============================================

const RECURSIVE_CONFIG = {
    DEFAULT_POINTS: 50,
    ANOMALY_PROBABILITY: 0.1,
    ANOMALY_MAGNITUDE: 8,
    ANOMALY_THRESHOLD: 2.0,
    TREND_WINDOW: 5
};

// ============================================
// ESTADO GLOBAL
// ============================================

const RecursiveState = {
    sensorData: [],
    analysisResult: null,
    chart: null,
    elements: {}
};

// ============================================
// DOM HANDLER
// ============================================

const DOMHandler = {
    init: function() {
        RecursiveState.elements = {
            dataPoints: document.getElementById('dataPoints'),
            dataMean: document.getElementById('dataMean'),
            dataRange: document.getElementById('dataRange'),
            
            peaksCount: document.getElementById('peaksCount'),
            peakValues: document.getElementById('peakValues'),
            peaksIndices: document.getElementById('peaksIndices'),
            
            trendsCount: document.getElementById('trendsCount'),
            longestTrend: document.getElementById('longestTrend'),
            
            anomaliesCount: document.getElementById('anomaliesCount'),
            anomalyThreshold: document.getElementById('anomalyThreshold'),
            anomaliesList: document.getElementById('anomaliesList'),
            
            maxSum: document.getElementById('maxSum'),
            maxLength: document.getElementById('maxLength'),
            maxRange: document.getElementById('maxRange'),
            
            insightText: document.getElementById('insightText'),
            sensorDataChart: document.getElementById('sensorDataChart')
        };
    }
};

// ============================================
// GENERADOR DE DATOS
// ============================================

const DataGenerator = {
    /**
     * Genera datos simulados con tendencia sinusoidal
     */
    generateData: function(numPoints = RECURSIVE_CONFIG.DEFAULT_POINTS, withAnomalies = true) {
        const data = [];
        let base = 20;
        
        for (let i = 0; i < numPoints; i++) {
            // Tendencia sinusoidal con ruido
            let trend = Math.sin(i / 8) * 5;
            let noise = (Math.random() - 0.5) * 1;
            let value = base + trend + noise;
            
            // Añadir algunos picos aleatorios
            if (withAnomalies && Math.random() < RECURSIVE_CONFIG.ANOMALY_PROBABILITY) {
                value += Math.random() * RECURSIVE_CONFIG.ANOMALY_MAGNITUDE;
            }
            
            data.push(Math.round(value * 10) / 10);
        }
        
        return data;
    },
    
    /**
     * Añade una anomalía en una posición aleatoria
     */
    addAnomaly: function(data) {
        if (data.length === 0) return data;
        
        const newData = [...data];
        const index = Math.floor(Math.random() * newData.length);
        newData[index] += Math.random() * 15 + 5;
        
        return newData;
    }
};

// ============================================
// ALGORITMOS DE ANÁLISIS
// ============================================

const RecursiveAlgorithms = {
    /**
     * Encuentra picos en los datos
     */
    findPeaks: function(data) {
        const peaks = [];
        
        // Versión iterativa (simulando recursión para el frontend)
        for (let i = 1; i < data.length - 1; i++) {
            if (data[i] > data[i-1] && data[i] > data[i+1]) {
                peaks.push(i);
            }
        }
        
        return peaks;
    },
    
    /**
     * Detecta tendencias crecientes
     */
    findTrends: function(data) {
        const trends = [];
        let currentTrend = [];
        
        for (let i = 0; i < data.length; i++) {
            if (currentTrend.length === 0) {
                currentTrend = [i];
            } else {
                const last = currentTrend[currentTrend.length - 1];
                if (data[i] > data[last]) {
                    currentTrend.push(i);
                } else {
                    if (currentTrend.length >= 2) {
                        trends.push(currentTrend);
                    }
                    currentTrend = [i];
                }
            }
        }
        
        if (currentTrend.length >= 2) {
            trends.push(currentTrend);
        }
        
        return trends;
    },
    
    /**
     * Encuentra anomalías estadísticas
     */
    findAnomalies: function(data, threshold = RECURSIVE_CONFIG.ANOMALY_THRESHOLD) {
        const anomalies = [];
        
        for (let i = 5; i < data.length; i++) {
            const window = data.slice(i-5, i);
            const mean = window.reduce((a, b) => a + b, 0) / 5;
            
            const variance = window.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / 5;
            const stdDev = Math.sqrt(variance);
            
            if (Math.abs(data[i] - mean) > threshold * stdDev && stdDev > 0) {
                anomalies.push({
                    index: i,
                    value: data[i],
                    mean: mean.toFixed(2),
                    deviation: (Math.abs(data[i] - mean) / stdDev).toFixed(2)
                });
            }
        }
        
        return anomalies;
    },
    
    /**
     * Encuentra el subarreglo de suma máxima (algoritmo de Kadane)
     */
    maxSubarray: function(data) {
        if (data.length === 0) return { start: 0, end: 0, sum: 0 };
        
        let maxSum = -Infinity;
        let maxStart = 0;
        let maxEnd = 0;
        
        for (let i = 0; i < data.length; i++) {
            let sum = 0;
            for (let j = i; j < data.length; j++) {
                sum += data[j];
                if (sum > maxSum) {
                    maxSum = sum;
                    maxStart = i;
                    maxEnd = j;
                }
            }
        }
        
        return {
            start: maxStart,
            end: maxEnd,
            sum: maxSum,
            length: maxEnd - maxStart + 1
        };
    },
    
    /**
     * Calcula estadísticas básicas
     */
    calculateStats: function(data) {
        if (data.length === 0) {
            return { mean: 0, min: 0, max: 0, range: 0 };
        }
        
        const sum = data.reduce((a, b) => a + b, 0);
        const mean = sum / data.length;
        const min = Math.min(...data);
        const max = Math.max(...data);
        
        return {
            mean: mean,
            min: min,
            max: max,
            range: max - min
        };
    }
};

// ============================================
// CHART MANAGER
// ============================================

const ChartManager = {
    init: function() {
        const ctx = RecursiveState.elements.sensorDataChart?.getContext('2d');
        if (!ctx) return;
        
        RecursiveState.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array.from({length: RecursiveState.sensorData.length}, (_, i) => i),
                datasets: [{
                    label: 'Temperatura (°C)',
                    data: RecursiveState.sensorData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 3,
                    pointBackgroundColor: function(context) {
                        const index = context.dataIndex;
                        const value = context.raw;
                        
                        // Colorear puntos según su naturaleza
                        if (RecursiveState.peaks && RecursiveState.peaks.includes(index)) {
                            return '#ef4444'; // Rojo para picos
                        }
                        if (RecursiveState.anomalies && 
                            RecursiveState.anomalies.some(a => a.index === index)) {
                            return '#f59e0b'; // Naranja para anomalías
                        }
                        return '#10b981'; // Verde normal
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { 
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                return `Valor: ${context.raw}°C`;
                            }
                        }
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
                        grid: { display: false },
                        ticks: { 
                            color: '#94a3b8',
                            maxTicksLimit: 10
                        },
                        title: {
                            display: true,
                            text: 'Índice',
                            color: '#94a3b8'
                        }
                    }
                }
            }
        });
    },
    
    update: function() {
        if (!RecursiveState.chart) return;
        
        RecursiveState.chart.data.datasets[0].data = RecursiveState.sensorData;
        RecursiveState.chart.data.labels = Array.from(
            {length: RecursiveState.sensorData.length}, (_, i) => i
        );
        RecursiveState.chart.update();
    }
};

// ============================================
// UI UPDATER
// ============================================

const UIUpdater = {
    updateBasicStats: function() {
        const stats = RecursiveAlgorithms.calculateStats(RecursiveState.sensorData);
        
        RecursiveState.elements.dataPoints.textContent = RecursiveState.sensorData.length;
        RecursiveState.elements.dataMean.textContent = stats.mean.toFixed(2);
        RecursiveState.elements.dataRange.textContent = stats.range.toFixed(2);
    },
    
    updatePeaks: function(peaks) {
        RecursiveState.peaks = peaks;
        
        RecursiveState.elements.peaksCount.textContent = peaks.length;
        
        if (peaks.length > 0) {
            const peakValues = peaks.map(i => RecursiveState.sensorData[i]);
            const avgPeak = peakValues.reduce((a, b) => a + b, 0) / peaks.length;
            RecursiveState.elements.peakValues.textContent = avgPeak.toFixed(2);
            
            const peaksHtml = peaks.slice(0, 10).map(i => 
                `<span class="peak-marker"></span>${i}`
            ).join(' ');
            RecursiveState.elements.peaksIndices.innerHTML = peaksHtml;
        } else {
            RecursiveState.elements.peakValues.textContent = '0';
            RecursiveState.elements.peaksIndices.textContent = '-';
        }
    },
    
    updateTrends: function(trends) {
        RecursiveState.elements.trendsCount.textContent = trends.length;
        
        const longestTrend = Math.max(...trends.map(t => t.length), 0);
        RecursiveState.elements.longestTrend.textContent = longestTrend;
    },
    
    updateAnomalies: function(anomalies) {
        RecursiveState.anomalies = anomalies;
        
        RecursiveState.elements.anomaliesCount.textContent = anomalies.length;
        RecursiveState.elements.anomalyThreshold.textContent = `${RECURSIVE_CONFIG.ANOMALY_THRESHOLD}σ`;
        
        if (anomalies.length > 0) {
            const anomaliesHtml = anomalies.slice(-5).map(a => 
                `<div style="margin: 5px 0; padding: 5px; background: #0f172a; border-radius: 5px;">
                    <span class="insight-badge badge-anomaly">Índice ${a.index}</span>
                    Valor: ${a.value} (${a.deviation}σ)
                </div>`
            ).join('');
            RecursiveState.elements.anomaliesList.innerHTML = anomaliesHtml;
        } else {
            RecursiveState.elements.anomaliesList.innerHTML = 
                '<span style="color: #94a3b8;">No hay anomalías detectadas</span>';
        }
    },
    
    updateMaxSubarray: function(maxSub) {
        RecursiveState.elements.maxSum.textContent = maxSub.sum.toFixed(2);
        RecursiveState.elements.maxLength.textContent = maxSub.length;
        RecursiveState.elements.maxRange.textContent = 
            `[${maxSub.start}, ${maxSub.end}] (${maxSub.length} puntos)`;
    },
    
    updateInsights: function(peaks, anomalies, trends) {
        const insightText = [];
        
        if (peaks.length > 0) {
            insightText.push(`Se detectaron ${peaks.length} picos de temperatura.`);
        }
        if (anomalies.length > 0) {
            insightText.push(`Se encontraron ${anomalies.length} anomalías estadísticas.`);
        }
        if (trends.length > 0) {
            const longestTrend = Math.max(...trends.map(t => t.length), 0);
            insightText.push(`Se identificaron ${trends.length} tendencias, la más larga de ${longestTrend} puntos.`);
        }
        
        RecursiveState.elements.insightText.innerHTML = 
            insightText.length > 0 ? 
            insightText.map(t => `<div>• ${t}</div>`).join('') : 
            'No se detectaron patrones significativos.';
    }
};

// ============================================
// APLICACIÓN PRINCIPAL
// ============================================

const RecursiveApp = {
    /**
     * Inicializa la aplicación
     */
    init: function() {
        console.log('🔄 Inicializando dashboard recursivo...');
        
        DOMHandler.init();
        this.generateNewData();
    },
    
    /**
     * Genera nuevos datos aleatorios
     */
    generateNewData: function() {
        RecursiveState.sensorData = DataGenerator.generateData(
            RECURSIVE_CONFIG.DEFAULT_POINTS, 
            true
        );
        
        if (!RecursiveState.chart) {
            ChartManager.init();
        } else {
            ChartManager.update();
        }
        
        this.runAnalysis();
    },
    
    /**
     * Añade una anomalía aleatoria
     */
    addAnomaly: function() {
        RecursiveState.sensorData = DataGenerator.addAnomaly(RecursiveState.sensorData);
        ChartManager.update();
        this.runAnalysis();
    },
    
    /**
     * Ejecuta el análisis completo
     */
    runAnalysis: function() {
        if (RecursiveState.sensorData.length === 0) return;
        
        // Ejecutar algoritmos
        const peaks = RecursiveAlgorithms.findPeaks(RecursiveState.sensorData);
        const trends = RecursiveAlgorithms.findTrends(RecursiveState.sensorData);
        const anomalies = RecursiveAlgorithms.findAnomalies(RecursiveState.sensorData);
        const maxSub = RecursiveAlgorithms.maxSubarray(RecursiveState.sensorData);
        
        // Actualizar UI
        UIUpdater.updateBasicStats();
        UIUpdater.updatePeaks(peaks);
        UIUpdater.updateTrends(trends);
        UIUpdater.updateAnomalies(anomalies);
        UIUpdater.updateMaxSubarray(maxSub);
        UIUpdater.updateInsights(peaks, anomalies, trends);
        
        // Actualizar gráfico para mostrar puntos coloreados
        ChartManager.update();
        
        console.log('✅ Análisis completado:', {
            peaks: peaks.length,
            trends: trends.length,
            anomalies: anomalies.length,
            maxSum: maxSub.sum
        });
    }
};

// ============================================
// EXPOSICIÓN GLOBAL
// ============================================

window.RecursiveApp = RecursiveApp;

// ============================================
// INICIALIZACIÓN
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    RecursiveApp.init();
});