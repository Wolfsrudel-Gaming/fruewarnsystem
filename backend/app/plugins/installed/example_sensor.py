"""
Beispiel-Plugin: Zeigt wie ein Collector-Plugin aufgebaut ist.
Kann als Template für eigene Plugins verwendet werden.

Benötigt:
  - name: str - Eindeutiger Name des Plugins
  - category: str - Kategorie (water, weather, fire, custom, ...)
  - interval_seconds: int - Abrufintervall
  - collect() -> list[dict] - Daten sammeln und zurückgeben
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExampleSensorCollector:
    name = "example_sensor"
    category = "custom"
    interval_seconds = 3600

    async def collect(self) -> list[dict]:
        # Hier eigene Sensorlogik implementieren
        # z.B. IoT-Sensor abfragen, externe API aufrufen, etc.
        logger.info(f"Example sensor collecting data at {datetime.utcnow()}")
        return []


# Das Plugin-System sucht nach dieser Variable
collector = ExampleSensorCollector()
