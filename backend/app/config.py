from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "DRK Troisdorf Frühwarnsystem"
    app_version: str = "1.0.0"
    debug: bool = False

    # Location
    center_lat: float = 50.8159
    center_lon: float = 7.1533
    default_radius_km: float = 30.0
    city_name: str = "Troisdorf"
    region: str = "Rhein-Sieg-Kreis"

    # Database
    database_url: str = "postgresql+asyncpg://fws:fws_secret@db:5432/fruewarnsystem"
    database_url_sync: str = "postgresql://fws:fws_secret@db:5432/fruewarnsystem"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 1440
    admin_username: str = "admin"
    admin_password: str = "CHANGE_ME"

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_group_id: Optional[str] = None

    # Firebase (FCM)
    firebase_credentials_path: Optional[str] = None

    # ntfy.sh
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: str = "drk-troisdorf-fws"

    # SMS (Twilio)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    alert_phone_number: Optional[str] = None

    # E-Mail
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_email: Optional[str] = None

    # Ollama (Local LLM)
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b"

    # MQTT / Home Assistant
    mqtt_broker: Optional[str] = None
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    ha_discovery_prefix: str = "homeassistant"

    # DWD
    dwd_station_id: str = "10513"  # MOSMIX-Station Köln/Bonn Flughafen

    # Pegel
    pegel_stations: str = "KOELN,BONN,TROISDORF,SIEGBURG"

    # Auto-Update
    auto_update_enabled: bool = True
    auto_update_check_interval_minutes: int = 30
    auto_update_branch: str = "main"
    auto_update_repo_url: str = ""
    auto_update_restart_delay_seconds: int = 10

    # Tankerkönig
    tankerkoenig_api_key: Optional[str] = None

    # Collector intervals (seconds)
    interval_weather: int = 300
    interval_water_normal: int = 3600
    interval_water_elevated: int = 300
    interval_fire: int = 1800
    interval_news: int = 600
    interval_traffic: int = 600
    interval_events: int = 3600
    interval_warnings: int = 120
    interval_air_quality: int = 1800
    interval_earthquake: int = 300
    interval_radiation: int = 1800
    interval_icu: int = 3600
    interval_grid: int = 900
    interval_shipping: int = 1800
    interval_transit: int = 600
    interval_fuel: int = 1800
    interval_drought: int = 21600
    interval_gdacs: int = 600
    interval_flood_warnings: int = 600
    interval_lightning: int = 300
    interval_feuerwehr_bonn: int = 120

    model_config = {"env_file": ".env", "env_prefix": "FWS_"}


settings = Settings()
