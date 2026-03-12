# realtime-sensor-monitoring
realtime-sensor-monitoring, Python, Materia INGENIERÍA DE SOFTWARE EN TIEMPO REAL

# Sistema de Monitoreo de Sensores con Algoritmos Recursivos

## Descripción del Proyecto

Este módulo extiende el sistema de monitoreo de sensores en tiempo real incorporando **algoritmos recursivos** para el análisis avanzado de patrones en series temporales. Los algoritmos implementados permiten detectar automáticamente picos, tendencias y anomalías en los datos de temperatura, proporcionando insights valiosos para el mantenimiento predictivo y la detección temprana de fallos.

## Problema Abordado

### Contexto
En sistemas de monitoreo industrial, los sensores generan grandes volúmenes de datos continuos. Detectar patrones significativos manualmente es imposible. Se necesitan algoritmos automatizados que puedan:

1. **Identificar picos anómalos** que podrían indicar fallos de equipo
2. **Detectar tendencias** que señalen degradación gradual
3. **Encontrar patrones** de comportamiento anormal
4. **Optimizar recursos** mediante análisis eficiente

### Solución Recursiva
Los algoritmos recursivos son ideales para este problema porque:
- **Dividen problemas complejos** en subproblemas más pequeños
- **Son naturales para datos secuenciales** como series temporales
- **Permiten backtracking** para explorar múltiples patrones
- **Son elegantes y mantenibles** con código limpio

## Algoritmos Recursivos Implementados

### 1. Búsqueda Recursiva de Picos (`find_peaks_recursive`)

**Problema:** Encontrar todos los puntos máximos locales en una serie de datos donde un valor es mayor que sus vecinos inmediatos.

**Aplicación:** Detectar momentos de temperatura inusualmente alta que podrían indicar sobrecalentamiento.

**Complejidad:** O(n) tiempo, O(n) espacio (por la pila de recursión)

### 2. Detección Recursiva de Tendencias (`detect_trend_recursive`)

**Problema:** Identificar todas las secuencias crecientes dentro de los datos.

**Aplicación:** Detectar calentamiento gradual o enfriamiento progresivo en equipos.

**Complejidad:** O(n²) en el peor caso, O(n log n) promedio

### 3. Búsqueda Recursiva de Anomalías (`find_anomalies_recursive`)

**Problema:** Encontrar puntos que se desvían significativamente de la media móvil.

**Aplicación:** Detectar lecturas anormales que podrían indicar fallos de sensor o condiciones peligrosas.

**Complejidad:** O(n × k) donde k es el tamaño de la ventana

### 4. Subarreglo Máximo (Divide y Vencerás) (`max_subarray_recursive`)

**Problema:** Encontrar el segmento contiguo con la suma máxima.

**Aplicación:** Identificar períodos de mayor actividad o consumo energético.

**Complejidad:** O(n log n) usando divide y vencerás

## Ejemplo de Uso

```python
from recursive_analyzer import recursive_analyzer

# Generar datos de prueba
sensor_data = recursive_analyzer.generate_test_data(100, with_anomalies=True)

# Analizar recursivamente
results = recursive_analyzer.analyze_sensor_data("sensor_temp_01", sensor_data)

print(f"📊 Picos detectados: {results['peaks']['count']}")
print(f"🚨 Anomalías encontradas: {results['anomalies']['count']}")
print(f"📈 Tendencias identificadas: {results['trends']['count']}")
