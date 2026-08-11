import json
import logging

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self):
        self.client = None
        self.connected = False

    def connect(self):
        if not settings.mqtt_broker:
            logger.info("MQTT broker not configured, skipping")
            return

        self.client = mqtt.Client(client_id="fws-backend", protocol=mqtt.MQTTv5)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        try:
            self.client.connect(settings.mqtt_broker, settings.mqtt_port)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.connected = True
        logger.info("Connected to MQTT broker")
        self._publish_ha_discovery()
        client.subscribe(f"{settings.ha_discovery_prefix}/sensor/fws/#")

    def _on_message(self, client, userdata, msg):
        logger.debug(f"MQTT message: {msg.topic} = {msg.payload}")

    def publish_scores(self, scores: dict):
        if not self.connected:
            return

        for category, data in scores.items():
            if category == "overall":
                topic = f"{settings.ha_discovery_prefix}/sensor/fws/overall/state"
            else:
                topic = f"{settings.ha_discovery_prefix}/sensor/fws/{category}/state"

            score = data.get("score", 0) if isinstance(data, dict) else 0
            self.client.publish(topic, json.dumps({
                "score": score,
                "detail": data.get("detail", "") if isinstance(data, dict) else "",
            }), retain=True)

    def _publish_ha_discovery(self):
        categories = {
            "overall": "Gesamtrisiko",
            "water": "Hochwasser",
            "weather": "Wetter",
            "fire": "Waldbrand",
            "traffic": "Verkehr",
            "air_quality": "Luftqualität",
            "official_warning": "Behördenwarnungen",
            "news": "Nachrichten",
        }

        for key, name in categories.items():
            config_topic = f"{settings.ha_discovery_prefix}/sensor/fws/{key}/config"
            state_topic = f"{settings.ha_discovery_prefix}/sensor/fws/{key}/state"

            config = {
                "name": f"FWS {name}",
                "unique_id": f"fws_{key}_score",
                "state_topic": state_topic,
                "value_template": "{{ value_json.score }}",
                "unit_of_measurement": "Score",
                "device": {
                    "identifiers": ["fws_drk_troisdorf"],
                    "name": "DRK Frühwarnsystem",
                    "model": "FWS v1.0",
                    "manufacturer": "DRK Troisdorf",
                },
                "icon": "mdi:alert-circle",
            }
            self.client.publish(config_topic, json.dumps(config), retain=True)

        logger.info("Published Home Assistant discovery configs")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


mqtt_bridge = MQTTBridge()
