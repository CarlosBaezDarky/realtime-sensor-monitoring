"""
Procesador de datos simplificado
"""

class DataProcessor:
    def __init__(self):
        self.is_active = True
    
    async def process(self, data):
        """Procesar datos de sensores"""
        return data  # Por ahora, solo retorna los datos sin cambios