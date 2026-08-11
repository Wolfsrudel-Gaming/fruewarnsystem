import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.models.database import init_db
from app.api.routes import dashboard, system, auth, webhooks, analysis
from app.api.websocket.manager import ws_manager
from app.collectors.water.pegel_collector import collect_water_levels
from app.collectors.water.hochwasser_collector import collect_flood_warnings
from app.collectors.water.drought_collector import collect_drought_data
from app.collectors.weather.dwd_collector import collect_dwd_warnings, collect_dwd_forecast, collect_radar_data
from app.collectors.weather.lightning_collector import collect_lightning
from app.collectors.fire.fire_collector import collect_fire_risk
from app.collectors.news.news_collector import collect_news
from app.collectors.warnings.nina_collector import collect_official_warnings
from app.collectors.warnings.feuerwehr_bonn_collector import collect_feuerwehr_bonn
from app.collectors.warnings.gdacs_collector import collect_gdacs_alerts
from app.collectors.traffic.traffic_collector import collect_traffic
from app.collectors.traffic.nrw_traffic_collector import collect_nrw_traffic
from app.collectors.seismic.earthquake_collector import collect_earthquakes
from app.collectors.radiation.bfs_collector import collect_radiation
from app.collectors.health.divi_collector import collect_icu_capacity
from app.collectors.power.grid_collector import collect_grid_status
from app.collectors.events.event_collector import collect_events
from app.collectors.shipping.rhine_collector import collect_shipping_warnings
from app.collectors.transit.vrs_collector import collect_transit_disruptions
from app.collectors.fuel.tankerkoenig_collector import collect_fuel_prices
from app.services.alert.alert_engine import calculate_risk_scores, check_thresholds_and_alert, seed_default_thresholds
from app.services.notification.notifier import send_daily_report
from app.services.auto_updater import updater

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_collector(name: str, func):
    try:
        logger.info(f"Running collector: {name}")
        result = await func()
        scores = await calculate_risk_scores()
        await check_thresholds_and_alert(scores)
        await ws_manager.broadcast({"type": "update", "source": name, "scores": _serialize_scores(scores)})
    except Exception as e:
        logger.error(f"Collector {name} failed: {e}", exc_info=True)


async def check_auto_update():
    try:
        update = await updater.check_for_updates()
        if update:
            logger.info(f"Update available: {update['current']} -> {update['available']}")
            logger.info(f"Changes:\n{update['changes']}")
            success = await updater.apply_update(update["full_hash"])
            if success:
                await ws_manager.broadcast({
                    "type": "system",
                    "event": "update_applied",
                    "from": update["current"],
                    "to": update["available"],
                })
    except Exception as e:
        logger.error(f"Auto-update check failed: {e}")


async def send_daily():
    try:
        scores = await calculate_risk_scores()
        await send_daily_report(scores)
    except Exception as e:
        logger.error(f"Daily report failed: {e}")


def _serialize_scores(scores: dict) -> dict:
    result = {}
    for key, val in scores.items():
        if isinstance(val, dict):
            result[key] = {k: v for k, v in val.items() if k != "raw_data"}
        else:
            result[key] = val
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    await init_db()
    await seed_default_thresholds()

    scheduler.add_job(run_collector, "interval", seconds=settings.interval_warnings,
                      args=["warnings", collect_official_warnings], id="warnings", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_weather,
                      args=["weather", collect_dwd_warnings], id="weather_warnings", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_weather,
                      args=["forecast", collect_dwd_forecast], id="weather_forecast", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_weather,
                      args=["radar", collect_radar_data], id="radar", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_water_normal,
                      args=["water", collect_water_levels], id="water", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_fire,
                      args=["fire", collect_fire_risk], id="fire", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_news,
                      args=["news", collect_news], id="news", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_traffic,
                      args=["traffic", collect_traffic], id="traffic", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_traffic,
                      args=["nrw_traffic", collect_nrw_traffic], id="nrw_traffic", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_earthquake,
                      args=["earthquakes", collect_earthquakes], id="earthquakes", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_radiation,
                      args=["radiation", collect_radiation], id="radiation", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_icu,
                      args=["icu", collect_icu_capacity], id="icu", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_grid,
                      args=["grid", collect_grid_status], id="grid", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_events,
                      args=["events", collect_events], id="events", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_shipping,
                      args=["shipping", collect_shipping_warnings], id="shipping", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_transit,
                      args=["transit", collect_transit_disruptions], id="transit", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_fuel,
                      args=["fuel", collect_fuel_prices], id="fuel", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_flood_warnings,
                      args=["flood_warnings", collect_flood_warnings], id="flood_warnings", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_drought,
                      args=["drought", collect_drought_data], id="drought", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_lightning,
                      args=["lightning", collect_lightning], id="lightning", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_gdacs,
                      args=["gdacs", collect_gdacs_alerts], id="gdacs", replace_existing=True)
    scheduler.add_job(run_collector, "interval", seconds=settings.interval_feuerwehr_bonn,
                      args=["feuerwehr_bonn", collect_feuerwehr_bonn], id="feuerwehr_bonn", replace_existing=True)

    if settings.auto_update_enabled:
        scheduler.add_job(
            check_auto_update, "interval",
            minutes=settings.auto_update_check_interval_minutes,
            id="auto_update", replace_existing=True,
        )

    scheduler.add_job(send_daily, "cron", hour=6, minute=0, id="daily_report", replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started with all collectors")

    asyncio.create_task(run_collector("initial_warnings", collect_official_warnings))
    asyncio.create_task(run_collector("initial_weather", collect_dwd_warnings))
    asyncio.create_task(run_collector("initial_water", collect_water_levels))

    yield

    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(system.router)
app.include_router(webhooks.router)
app.include_router(analysis.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_personal(websocket, {"type": "pong"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": settings.app_name, "version": settings.app_version, "status": "running"}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
