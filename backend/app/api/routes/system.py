from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import UpdateLog, SystemLog
from app.services.auto_updater import updater
from app.config import settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status():
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "update_status": await updater.get_update_status(),
        "uptime": datetime.utcnow().isoformat(),
        "config": {
            "center": {"lat": settings.center_lat, "lon": settings.center_lon},
            "radius_km": settings.default_radius_km,
            "city": settings.city_name,
            "region": settings.region,
        },
    }


@router.get("/health")
async def health_check():
    checks = {}

    try:
        from app.models.database import engine
        async with engine.connect() as conn:
            await conn.execute(select(1))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}


@router.get("/updates/check")
async def check_updates():
    update = await updater.check_for_updates()
    if update:
        return {"update_available": True, **update}
    return {"update_available": False, "status": "up to date"}


@router.post("/updates/apply")
async def apply_update():
    update = await updater.check_for_updates()
    if not update:
        return {"status": "no update available"}

    success = await updater.apply_update(update["full_hash"])
    return {
        "status": "success" if success else "failed",
        "from": update["current"],
        "to": update["available"],
    }


@router.get("/updates/history")
async def update_history(db: AsyncSession = Depends(get_db)):
    stmt = select(UpdateLog).order_by(desc(UpdateLog.started_at)).limit(20)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "updates": [
            {
                "id": l.id,
                "from": l.version_from,
                "to": l.version_to,
                "commit": l.commit_hash,
                "status": l.status,
                "details": l.details,
                "started_at": l.started_at.isoformat() if l.started_at else None,
                "completed_at": l.completed_at.isoformat() if l.completed_at else None,
            }
            for l in logs
        ]
    }


@router.post("/updates/toggle")
async def toggle_auto_update(enabled: bool = True):
    settings.auto_update_enabled = enabled
    return {"auto_update_enabled": settings.auto_update_enabled}


@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    level: str = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SystemLog).order_by(desc(SystemLog.created_at)).limit(limit)
    if level:
        stmt = stmt.where(SystemLog.level == level.upper())

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": l.id,
                "component": l.component,
                "level": l.level,
                "message": l.message,
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    }
