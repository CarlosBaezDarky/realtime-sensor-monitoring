"""
Motor de alertas simplificado
"""

class AlertEngine:
    def __init__(self):
        self.is_active = True
    
    async def check_alerts(self, data):
        """Verificar condiciones de alerta"""
        return []  # Por ahora, no genera alertas