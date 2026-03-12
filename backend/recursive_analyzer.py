"""
Módulo de análisis recursivo para detección de patrones en datos de sensores
Implementa algoritmos recursivos para encontrar secuencias anómalas
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import random
import math

logger = logging.getLogger(__name__)

class RecursivePatternAnalyzer:
    """
    Analizador recursivo de patrones en datos de sensores
    Utiliza recursión para encontrar secuencias anómalas y tendencias
    """
    
    def __init__(self):
        self.analysis_history = []
        logger.info("🔍 Inicializado Analizador Recursivo de Patrones")
    
    # ============================================
    # ALGORITMO 1: BÚSQUEDA RECURSIVA DE PICOS
    # ============================================
    
    def find_peaks_recursive(self, data: List[float], index: int = 0, peaks: List[int] = None) -> List[int]:
        """
        Encuentra recursivamente todos los picos en una serie de datos
        Un pico es un punto donde el valor es mayor que sus vecinos
        
        Args:
            data: Lista de valores numéricos
            index: Índice actual en la recursión
            peaks: Lista acumulada de índices de picos encontrados
            
        Returns:
            Lista de índices donde se encuentran picos
        """
        # Inicializar lista de picos en la primera llamada
        if peaks is None:
            peaks = []
        
        # Caso base: hemos llegado al final de los datos
        if index >= len(data):
            return peaks
        
        # Verificar si el punto actual es un pico (necesita vecinos)
        if 1 <= index <= len(data) - 2:
            if data[index] > data[index-1] and data[index] > data[index+1]:
                peaks.append(index)
                logger.debug(f"📈 Pico encontrado en índice {index}: {data[index]}")
        
        # Llamada recursiva con el siguiente índice
        return self.find_peaks_recursive(data, index + 1, peaks)
    
    # ============================================
    # ALGORITMO 2: DETECCIÓN RECURSIVA DE TENDENCIAS
    # ============================================
    
    def detect_trend_recursive(self, data: List[float], start: int = 0, current_trend: List[int] = None, 
                                all_trends: List[List[int]] = None) -> List[List[int]]:
        """
        Detecta recursivamente todas las tendencias (secuencias crecientes) en los datos
        
        Args:
            data: Lista de valores
            start: Índice de inicio para la búsqueda actual
            current_trend: Tendencia actual siendo construida
            all_trends: Lista de todas las tendencias encontradas
            
        Returns:
            Lista de listas con los índices de cada tendencia
        """
        if all_trends is None:
            all_trends = []
        if current_trend is None:
            current_trend = []
        
        # Caso base: hemos recorrido todos los datos
        if start >= len(data):
            if len(current_trend) >= 2:  # Guardar la última tendencia si tiene al menos 2 puntos
                all_trends.append(current_trend)
            return all_trends
        
        # Si la tendencia actual está vacía, comenzar una nueva
        if not current_trend:
            current_trend.append(start)
            return self.detect_trend_recursive(data, start + 1, current_trend, all_trends)
        
        # Verificar si el siguiente punto continúa la tendencia creciente
        last_idx = current_trend[-1]
        if start < len(data) and data[start] > data[last_idx]:
            # Continúa la tendencia
            current_trend.append(start)
            return self.detect_trend_recursive(data, start + 1, current_trend, all_trends)
        else:
            # La tendencia terminó
            if len(current_trend) >= 2:  # Guardar si tiene al menos 2 puntos
                all_trends.append(current_trend)
            # Comenzar nueva tendencia desde la posición actual
            return self.detect_trend_recursive(data, start, [], all_trends)
    
    # ============================================
    # ALGORITMO 3: BÚSQUEDA RECURSIVA DE ANOMALÍAS
    # ============================================
    
    def find_anomalies_recursive(self, data: List[float], threshold: float, 
                                   index: int = 0, anomalies: List[Dict] = None) -> List[Dict]:
        """
        Encuentra recursivamente anomalías basadas en desviación de la media móvil
        
        Args:
            data: Lista de valores
            threshold: Umbral de desviación para considerar anomalía
            index: Índice actual
            anomalies: Lista acumulada de anomalías encontradas
            
        Returns:
            Lista de diccionarios con información de anomalías
        """
        if anomalies is None:
            anomalies = []
        
        # Caso base: hemos llegado al final
        if index >= len(data):
            return anomalies
        
        # Necesitamos al menos 5 puntos para calcular media móvil
        if index >= 5:
            # Calcular media de los últimos 5 puntos (recursivamente)
            mean = self._calculate_mean_recursive(data, index - 5, index)
            
            # Calcular desviación estándar
            std_dev = self._calculate_std_dev_recursive(data, index - 5, index, mean)
            
            # Verificar si el punto actual es una anomalía
            if abs(data[index] - mean) > threshold * std_dev:
                anomaly = {
                    "index": index,
                    "value": data[index],
                    "mean": mean,
                    "std_dev": std_dev,
                    "deviation": abs(data[index] - mean) / std_dev if std_dev > 0 else 0,
                    "timestamp": datetime.now().isoformat()
                }
                anomalies.append(anomaly)
                logger.info(f"🚨 Anomalía detectada en índice {index}: {data[index]} (desviación: {anomaly['deviation']:.2f}σ)")
        
        # Llamada recursiva
        return self.find_anomalies_recursive(data, threshold, index + 1, anomalies)
    
    def _calculate_mean_recursive(self, data: List[float], start: int, end: int, 
                                    current_sum: float = 0, count: int = 0) -> float:
        """Calcula recursivamente la media de un segmento de datos"""
        if start >= end:
            return current_sum / count if count > 0 else 0
        
        return self._calculate_mean_recursive(data, start + 1, end, 
                                                current_sum + data[start], count + 1)
    
    def _calculate_std_dev_recursive(self, data: List[float], start: int, end: int, 
                                       mean: float, sum_sq_diff: float = 0, count: int = 0) -> float:
        """Calcula recursivamente la desviación estándar"""
        if start >= end:
            return math.sqrt(sum_sq_diff / count) if count > 0 else 0
        
        diff = data[start] - mean
        return self._calculate_std_dev_recursive(data, start + 1, end, mean,
                                                   sum_sq_diff + diff * diff, count + 1)
    
    # ============================================
    # ALGORITMO 4: BÚSQUEDA DE SUBARREGLO MÁXIMO (DIVIDE Y VENCERÁS)
    # ============================================
    
    def max_subarray_recursive(self, data: List[float], low: int, high: int) -> Tuple[int, int, float]:
        """
        Encuentra el subarreglo contiguo con la suma máxima usando divide y vencerás
        
        Args:
            data: Lista de valores
            low: Índice inferior
            high: Índice superior
            
        Returns:
            Tupla (inicio, fin, suma) del subarreglo máximo
        """
        # Caso base: un solo elemento
        if low == high:
            return low, high, data[low]
        
        # Dividir el arreglo en dos mitades
        mid = (low + high) // 2
        
        # Conquistar recursivamente ambas mitades
        left_start, left_end, left_sum = self.max_subarray_recursive(data, low, mid)
        right_start, right_end, right_sum = self.max_subarray_recursive(data, mid + 1, high)
        
        # Combinar: encontrar el subarreglo que cruza la mitad
        cross_start, cross_end, cross_sum = self._max_crossing_subarray(data, low, mid, high)
        
        # Devolver el mejor de los tres
        if left_sum >= right_sum and left_sum >= cross_sum:
            return left_start, left_end, left_sum
        elif right_sum >= left_sum and right_sum >= cross_sum:
            return right_start, right_end, right_sum
        else:
            return cross_start, cross_end, cross_sum
    
    def _max_crossing_subarray(self, data: List[float], low: int, mid: int, high: int) -> Tuple[int, int, float]:
        """Encuentra el subarreglo máximo que cruza el punto medio"""
        # Suma máxima hacia la izquierda desde mid
        left_sum = float('-inf')
        sum_temp = 0
        max_left = mid
        
        for i in range(mid, low - 1, -1):
            sum_temp += data[i]
            if sum_temp > left_sum:
                left_sum = sum_temp
                max_left = i
        
        # Suma máxima hacia la derecha desde mid+1
        right_sum = float('-inf')
        sum_temp = 0
        max_right = mid + 1
        
        for i in range(mid + 1, high + 1):
            sum_temp += data[i]
            if sum_temp > right_sum:
                right_sum = sum_temp
                max_right = i
        
        return max_left, max_right, left_sum + right_sum
    
    # ============================================
    # GENERADOR DE DATOS DE PRUEBA
    # ============================================
    
    def generate_test_data(self, num_points: int = 100, with_anomalies: bool = True) -> List[float]:
        """Genera datos de prueba para los algoritmos recursivos"""
        data = []
        base = 20.0  # Temperatura base
        
        for i in range(num_points):
            # Tendencia suave con algo de ruido
            trend = math.sin(i / 10) * 5  # Onda sinusoidal
            noise = random.gauss(0, 0.5)  # Ruido gaussiano
            value = base + trend + noise
            
            # Añadir algunas anomalías
            if with_anomalies and random.random() < 0.05:  # 5% de probabilidad
                value += random.uniform(10, 20)  # Pico anómalo
            
            data.append(round(value, 2))
        
        return data
    
    # ============================================
    # ANÁLISIS COMPLETO
    # ============================================
    
    def analyze_sensor_data(self, sensor_id: str, data: List[float]) -> Dict[str, Any]:
        """
        Realiza un análisis completo de los datos del sensor usando algoritmos recursivos
        """
        logger.info(f"🔬 Analizando datos del sensor {sensor_id} ({len(data)} puntos)")
        
        # Encontrar picos
        peaks = self.find_peaks_recursive(data)
        
        # Detectar tendencias
        trends = self.detect_trend_recursive(data)
        
        # Encontrar anomalías
        anomalies = self.find_anomalies_recursive(data, threshold=2.0)
        
        # Encontrar subarreglo máximo (para detectar períodos de alta actividad)
        if data:
            max_start, max_end, max_sum = self.max_subarray_recursive(data, 0, len(data) - 1)
        else:
            max_start, max_end, max_sum = 0, 0, 0
        
        # Calcular estadísticas básicas recursivamente
        mean = self._calculate_mean_recursive(data, 0, len(data))
        
        result = {
            "sensor_id": sensor_id,
            "timestamp": datetime.now().isoformat(),
            "data_points": len(data),
            "mean": round(mean, 2),
            "peaks": {
                "count": len(peaks),
                "indices": peaks[:10],  # Primeros 10 picos
                "values": [data[i] for i in peaks[:10]]
            },
            "trends": {
                "count": len(trends),
                "longest_trend": max([len(t) for t in trends], default=0),
                "trends_detected": len(trends)
            },
            "anomalies": {
                "count": len(anomalies),
                "details": anomalies[-5:]  # Últimas 5 anomalías
            },
            "max_subarray": {
                "start": max_start,
                "end": max_end,
                "sum": round(max_sum, 2),
                "length": max_end - max_start + 1
            }
        }
        
        # Guardar en historial
        self.analysis_history.append(result)
        
        return result
    
    def get_analysis_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene el historial de análisis"""
        return self.analysis_history[-limit:]


# Instancia global
recursive_analyzer = RecursivePatternAnalyzer()