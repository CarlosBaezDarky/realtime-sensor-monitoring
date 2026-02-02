"""
Simulador de sensores simplificado
"""
import random
from datetime import datetime, timezone

class SensorSimulator:
    def __init__(self):
        self.is_active = False
    
    async def start(self):
        """Iniciar simulador"""
        self.is_active = True
    
    def generate_data(self):
        """Generar datos de sensores simulados"""
        return {
            "sensor_id": f"sensor_{random.randint(1, 5):03d}",
            "sensor_type": random.choice(["temperature", "humidity", "pressure"]),
            "value": round(random.uniform(20.0, 30.0), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": random.choice(["Sala Principal", "Exterior", "Oficina"])
        }