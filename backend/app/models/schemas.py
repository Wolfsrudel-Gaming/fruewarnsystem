import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, Boolean, Enum, JSON,
    Index, func
)
from sqlalchemy.dialects.postgresql import JSONB
from app.models.database import Base


class AlertCategory(str, enum.Enum):
    WATER = "water"
    WEATHER = "weather"
    FIRE = "fire"
    TRAFFIC = "traffic"
    MANV = "manv"
    AIR_QUALITY = "air_quality"
    NEWS = "news"
    OFFICIAL_WARNING = "official_warning"
    SEISMIC = "seismic"
    RADIATION = "radiation"
    HEALTH = "health"
    POWER = "power"
    EVENTS = "events"
    SHIPPING = "shipping"
    CUSTOM = "custom"


class WaterLevel(Base):
    __tablename__ = "water_levels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), nullable=False, index=True)
    station_name = Column(String(200))
    river = Column(String(100))
    level_cm = Column(Float)
    flow_m3s = Column(Float, nullable=True)
    trend = Column(String(20))  # rising, falling, stable
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    classification = Column(JSONB, nullable=True)  # von classify_water_level (Duerre/Hochwasser)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_water_levels_station_time", "station_id", "timestamp"),
    )


class WeatherData(Base):
    __tablename__ = "weather_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String(50), nullable=False, index=True)  # warning, radar, forecast, measurement
    region = Column(String(200))
    severity = Column(Integer, default=0)
    title = Column(String(500))
    description = Column(Text)
    parameters = Column(JSONB, nullable=True)
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_weather_data_type_time", "data_type", "created_at"),
    )


class FireRisk(Base):
    __tablename__ = "fire_risk"
    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(200))
    risk_index = Column(Integer)  # 1-5 DWD scale
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)
    wind_direction = Column(Float, nullable=True)
    rain_last_24h = Column(Float, nullable=True)
    satellite_hotspots = Column(JSONB, nullable=True)
    source = Column(String(100))
    timestamp = Column(DateTime, nullable=False)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class AirQuality(Base):
    __tablename__ = "air_quality"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), index=True)
    station_name = Column(String(200))
    pm25 = Column(Float, nullable=True)
    pm10 = Column(Float, nullable=True)
    ozone = Column(Float, nullable=True)
    no2 = Column(Float, nullable=True)
    aqi = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class NewsItem(Base):
    __tablename__ = "news_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    url = Column(String(1000))
    source = Column(String(200))
    category = Column(String(100))
    relevance_score = Column(Float, default=0.0)
    is_relevant = Column(Boolean, default=False)
    ai_analysis = Column(JSONB, nullable=True)
    published_at = Column(DateTime)
    content_hash = Column(String(64), unique=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_news_relevance", "is_relevant", "created_at"),
    )


class OfficialWarning(Base):
    __tablename__ = "official_warnings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    warning_id = Column(String(200), unique=True)
    source_system = Column(String(50))  # nina, katwarn, mowas, eu_alert
    severity = Column(String(20))
    urgency = Column(String(20))
    category = Column(String(50))
    headline = Column(String(500))
    description = Column(Text)
    instruction = Column(Text, nullable=True)
    area_description = Column(String(500))
    area_geocode = Column(JSONB, nullable=True)
    effective = Column(DateTime)
    expires = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class TrafficEvent(Base):
    __tablename__ = "traffic_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(200), unique=True)
    road = Column(String(100))
    event_type = Column(String(50))  # accident, construction, jam, closure
    title = Column(String(500))
    description = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    severity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    source = Column(String(100))
    started_at = Column(DateTime)
    ended_at = Column(DateTime, nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class EventCalendar(Base):
    __tablename__ = "event_calendar"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(500))
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    expected_visitors = Column(Integer, nullable=True)
    risk_score = Column(Float, default=0.0)
    starts_at = Column(DateTime)
    ends_at = Column(DateTime, nullable=True)
    source = Column(String(200))
    is_manual = Column(Boolean, default=False)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(AlertCategory), nullable=False)
    score = Column(Float, nullable=False)  # 0-100
    title = Column(String(500), nullable=False)
    description = Column(Text)
    source_data = Column(JSONB, nullable=True)
    threshold_config = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    escalation_level = Column(Integer, default=0)  # 0=none, 1=push, 2=telegram, 3=sms, 4=call
    notifications_sent = Column(JSONB, default=list)
    triggered_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_alerts_active", "is_active", "category"),
        Index("ix_alerts_score", "score"),
    )


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(AlertCategory), nullable=False)
    score = Column(Float, nullable=False)
    components = Column(JSONB)
    calculated_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_risk_scores_category_time", "category", "calculated_at"),
    )


class AlertThreshold(Base):
    __tablename__ = "alert_thresholds"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(AlertCategory), nullable=False)
    name = Column(String(200), nullable=False)
    condition = Column(JSONB, nullable=False)
    score_contribution = Column(Float, default=10.0)
    notification_channels = Column(JSONB, default=list)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SoilMoisture(Base):
    __tablename__ = "soil_moisture"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), index=True)
    region = Column(String(200))
    moisture_percent = Column(Float)
    drought_index = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class LightningData(Base):
    __tablename__ = "lightning_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    amplitude = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_lightning_time", "timestamp"),
    )


class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False)
    message = Column(Text)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class UpdateLog(Base):
    __tablename__ = "update_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    version_from = Column(String(50))
    version_to = Column(String(50))
    commit_hash = Column(String(40))
    status = Column(String(20))
    details = Column(Text, nullable=True)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)


class EarthquakeEvent(Base):
    __tablename__ = "earthquake_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(200), unique=True)
    magnitude = Column(Float)
    depth_km = Column(Float, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    location = Column(String(500))
    region = Column(String(200))
    event_time = Column(DateTime, nullable=False)
    felt_reports = Column(Integer, nullable=True)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_earthquake_time", "event_time"),
    )


class RadiationReading(Base):
    __tablename__ = "radiation_readings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), index=True)
    station_name = Column(String(200))
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    gamma_dose_rate = Column(Float)  # nSv/h
    is_elevated = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class ICUCapacity(Base):
    __tablename__ = "icu_capacity"
    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String(50), index=True)
    region_name = Column(String(200))
    beds_total = Column(Integer)
    beds_occupied = Column(Integer)
    beds_free = Column(Integer)
    ventilator_occupied = Column(Integer, nullable=True)
    ventilator_free = Column(Integer, nullable=True)
    occupancy_rate = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class GridStatus(Base):
    __tablename__ = "grid_status"
    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(200))
    generation_mw = Column(Float, nullable=True)
    consumption_mw = Column(Float, nullable=True)
    balance_mw = Column(Float, nullable=True)
    renewable_share = Column(Float, nullable=True)
    price_eur_mwh = Column(Float, nullable=True)
    is_stressed = Column(Boolean, default=False)
    stress_indicator = Column(String(200), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class RiverShippingWarning(Base):
    __tablename__ = "river_shipping_warnings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    warning_id = Column(String(200), unique=True)
    river = Column(String(100))
    section = Column(String(200), nullable=True)
    warning_type = Column(String(100))
    title = Column(String(500))
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class FuelStation(Base):
    __tablename__ = "fuel_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(100), index=True)
    name = Column(String(300))
    lat = Column(Float)
    lon = Column(Float)
    diesel = Column(Float, nullable=True)
    e5 = Column(Float, nullable=True)
    e10 = Column(Float, nullable=True)
    is_open = Column(Boolean, default=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class TransitDisruption(Base):
    __tablename__ = "transit_disruptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(String(200), unique=True, nullable=True)
    line = Column(String(100))
    route = Column(String(500), nullable=True)
    disruption_type = Column(String(50))
    title = Column(String(500))
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class DroughtData(Base):
    __tablename__ = "drought_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(200))
    soil_moisture_index = Column(Float, nullable=True)
    drought_class = Column(String(50), nullable=True)
    topsoil_moisture = Column(Float, nullable=True)
    deep_soil_moisture = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class FloodWarningLevel(Base):
    __tablename__ = "flood_warning_levels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(100), index=True)
    station_name = Column(String(200))
    river = Column(String(100))
    warning_level = Column(Integer)  # 0-4
    level_cm = Column(Float, nullable=True)
    trend = Column(String(20), nullable=True)
    state = Column(String(50))
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class GDACAlert(Base):
    __tablename__ = "gdac_alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(200), unique=True)
    alert_type = Column(String(50))  # earthquake, flood, cyclone, volcano
    title = Column(String(500))
    description = Column(Text, nullable=True)
    severity = Column(String(50))
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    country = Column(String(100), nullable=True)
    distance_km = Column(Float, nullable=True)
    event_time = Column(DateTime, nullable=True)
    source = Column(String(100))
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())


class FeedbackOutcome(str, enum.Enum):
    """Rueckmeldung, was aus einem Alarm tatsaechlich geworden ist."""
    EINSATZ = "einsatz"            # Echter Einsatz — Alarm war richtig (True Positive)
    VORSORGE = "vorsorge"          # Kein Einsatz, aber Vorwarnung war berechtigt (halber Treffer)
    KEIN_EINSATZ = "kein_einsatz"  # Fehlalarm (False Positive)
    UNKLAR = "unklar"              # Nicht bewertbar — fliesst nicht ins Lernen ein


class AlertFeedback(Base):
    """Rueckmeldung der Einsatzkraefte zu einem ausgeloesten Alarm.

    Basis fuer die Kalibrierung: Ohne diese Rueckmeldung kann das System
    nicht wissen, ob seine Warnungen tatsaechlich getroffen haben.
    """
    __tablename__ = "alert_feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, nullable=False, index=True)
    category = Column(Enum(AlertCategory), nullable=False)
    outcome = Column(Enum(FeedbackOutcome), nullable=False)
    alert_score = Column(Float, nullable=True)      # Score zum Alarmzeitpunkt
    deployment_type = Column(String(200), nullable=True)  # z.B. "Sandsackverbau", "Betreuung"
    forces_count = Column(Integer, nullable=True)   # Eingesetzte Kraefte
    severity_rating = Column(Integer, nullable=True)  # 1-5, subjektive Einsatzschwere
    lead_time_minutes = Column(Integer, nullable=True)  # Vorlauf des Alarms vor dem Einsatz
    notes = Column(Text, nullable=True)
    reported_by = Column(String(200), nullable=True)
    score_snapshot = Column(JSONB, nullable=True)   # Score-Zusammensetzung fuer Nachanalyse
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_feedback_cat_outcome", "category", "outcome"),
    )


class Deployment(Base):
    """Echter Einsatz — auch nachtraeglich und ohne vorherigen Alarm erfassbar.

    Einsaetze ohne Alarm sind die wichtigste Lernquelle: Sie zeigen, wo das
    System blind war (False Negatives).
    """
    __tablename__ = "deployments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(AlertCategory), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    forces_count = Column(Integer, nullable=True)
    severity_rating = Column(Integer, nullable=True)  # 1-5
    was_predicted = Column(Boolean, default=False)    # Gab es einen passenden Alarm?
    matched_alert_id = Column(Integer, nullable=True)
    reported_by = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_deployments_cat_time", "category", "occurred_at"),
    )


class CategoryCalibration(Base):
    """Gelernte Anpassung pro Kategorie.

    weight_multiplier wirkt auf das Kategoriegewicht im Gesamtscore,
    threshold_offset verschiebt die Ausloeseschwelle (negativ = frueher warnen).
    """
    __tablename__ = "category_calibration"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(AlertCategory), nullable=False, unique=True)
    weight_multiplier = Column(Float, default=1.0)
    threshold_offset = Column(Float, default=0.0)
    true_positives = Column(Integer, default=0)
    partial_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    sample_count = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)  # Manuell fixiert, kein Auto-Lernen
    last_adjustment_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PowerOutage(Base):
    """Konkreter Stromausfall aus der Stoerungsauskunft der Netzbetreiber.

    Zwei Quellen mit unterschiedlicher Verlaesslichkeit:
      * confirmed  — vom Netzbetreiber gemeldet, belastbar
      * reported   — Buergermeldung, frueher da, aber einzeln wenig aussagekraeftig
                     (kann auch eine durchgebrannte Sicherung im Haus sein)
    """
    __tablename__ = "power_outages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), index=True)     # id der Quelle
    kind = Column(String(20), default="confirmed")    # confirmed | reported
    operator_name = Column(String(200), nullable=True)
    postal_code = Column(String(20), nullable=True, index=True)
    city = Column(String(200), nullable=True)
    district = Column(String(200), nullable=True)
    street = Column(String(300), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True, index=True)
    radius_m = Column(Float, nullable=True)
    report_count = Column(Integer, default=1)         # gebuendelte Meldungen
    started_at = Column(DateTime, nullable=True)
    expected_end = Column(DateTime, nullable=True)
    last_update = Column(DateTime, nullable=True)
    is_fixed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    info = Column(Text, nullable=True)
    source = Column(String(100), default="stoerungsauskunft")
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_outage_active_dist", "is_active", "distance_km"),
        Index("ix_outage_kind", "kind", "is_active"),
    )


class SituationReportCache(Base):
    """Zwischengespeicherter KI-Lagebericht.

    Die Erzeugung ueber das lokale LLM dauert bis zu drei Minuten. Das ist
    laenger als jeder sinnvolle HTTP-Timeout (App 90s, Nginx meist 60s) —
    live erzeugt lief der Bericht deshalb regelmaessig ins Leere. Er wird
    daher im Hintergrund erstellt und hier abgelegt; der Endpunkt liefert
    sofort aus.
    """
    __tablename__ = "situation_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report = Column(Text, nullable=False)
    llm_generated = Column(Boolean, default=False)
    model = Column(String(100), nullable=True)
    context_summary = Column(JSONB, nullable=True)
    generation_seconds = Column(Float, nullable=True)
    generated_at = Column(DateTime, default=func.now(), index=True)


class KnowledgeScope(str, enum.Enum):
    """Geltungsbereich eines Wissenseintrags — von der eigenen Bereitschaft
    bis zur Bundesebene. Bestimmt, wie stark ein Eintrag die Lagebewertung
    fuer Troisdorf beeinflusst."""
    TROISDORF = "troisdorf"
    RHEIN_SIEG = "rhein_sieg"
    NRW = "nrw"
    BUND = "bund"


class KnowledgeKind(str, enum.Enum):
    """Art des Wissens. Steuert, wo ein Eintrag herangezogen wird."""
    # Was gilt: Gesetze, Konzepte, Bedarfsplaene
    DOKTRIN = "doktrin"
    # Wer ist da: Einheiten, Fachdienste, Standorte, Staerken
    ORGANISATION = "organisation"
    # Was kann passieren: Gefahrenobjekte, Risikoschwerpunkte
    GEFAHRENOBJEKT = "gefahrenobjekt"
    # Ab wann was: MANV-Stufen, Alarmstufen, Schwellen
    ESKALATIONSSTUFE = "eskalationsstufe"
    # Woran man es erkennt: Ausloeser, die zu einem Einsatz fuehren
    AUSLOESER = "ausloeser"
    # Womit: Fahrzeuge, Material, Kapazitaeten
    RESSOURCE = "ressource"
    # Erfahrungswissen aus eigenen Einsaetzen
    ERFAHRUNG = "erfahrung"


class KnowledgeEntry(Base):
    """Ein Baustein der DRK-Wissensdatenbank.

    Das System bewertet Lagen bisher rein aus Messwerten. Es weiss, dass ein
    Wert hoch ist — aber nicht, was das fuer Troisdorf bedeutet. Diese Tabelle
    haelt das Einsatzwissen dahinter: welche Stufen es gibt, welche Einheiten
    dann laufen, welche Gefahrenobjekte im Gebiet liegen.

    Zwei Herkuenfte werden bewusst getrennt gehalten:

    * ``is_official`` mit Quellenangabe — recherchiert aus oeffentlichen
      Dokumenten (Rettungsdienstbedarfsplan, Landeskonzepte, Gesetze).
    * eigene Eintraege ohne Quelle — internes Wissen, das die Nutzer selbst
      einpflegen. Die AAO des Kreises ist nicht oeffentlich; wer sie kennt,
      traegt sie hier ein.

    ``categories`` verbindet den Eintrag mit den Risikokategorien des
    Scorings, ``trigger`` beschreibt maschinenlesbar, ab wann er greift.
    """
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(Enum(KnowledgeKind), nullable=False, index=True)
    scope = Column(Enum(KnowledgeScope), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    # Risikokategorien (AlertCategory-Werte), fuer die der Eintrag zaehlt
    categories = Column(JSONB, default=list)
    # Freie Schlagworte fuer die Textsuche
    tags = Column(JSONB, default=list)
    # Maschinenlesbare Bedingung, z. B. {"category": "weather", "min_score": 70}
    trigger = Column(JSONB, nullable=True)
    # Zahlenwerte des Eintrags, z. B. {"patienten_max": 50, "helfer": 78}
    facts = Column(JSONB, nullable=True)
    source = Column(String(300), nullable=True)
    source_url = Column(String(1000), nullable=True)
    source_date = Column(String(50), nullable=True)
    is_official = Column(Boolean, default=False)
    # Eindeutiger Schluessel der Seed-Daten; eigene Eintraege haben keinen.
    # Verhindert Dubletten beim wiederholten Einspielen.
    seed_key = Column(String(120), nullable=True, unique=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_knowledge_kind_scope", "kind", "scope"),
    )
