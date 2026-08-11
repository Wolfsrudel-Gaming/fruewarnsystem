from datetime import datetime

from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.websocket.manager import ws_manager
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class IncomingWebhook(BaseModel):
    source: str
    event_type: str
    data: dict
    timestamp: Optional[str] = None


class OutgoingWebhookConfig(BaseModel):
    url: str
    events: list[str]
    secret: Optional[str] = None
    is_enabled: bool = True


_outgoing_webhooks: list[dict] = []


@router.post("/incoming")
async def receive_webhook(webhook: IncomingWebhook):
    await ws_manager.broadcast({
        "type": "webhook",
        "source": webhook.source,
        "event_type": webhook.event_type,
        "data": webhook.data,
        "timestamp": webhook.timestamp or datetime.utcnow().isoformat(),
    })
    return {"status": "received"}


@router.get("/outgoing")
async def list_outgoing_webhooks(user=Depends(get_current_user)):
    return {"webhooks": _outgoing_webhooks}


@router.post("/outgoing")
async def add_outgoing_webhook(config: OutgoingWebhookConfig, user=Depends(get_current_user)):
    webhook = config.model_dump()
    webhook["id"] = len(_outgoing_webhooks) + 1
    webhook["created_at"] = datetime.utcnow().isoformat()
    _outgoing_webhooks.append(webhook)
    return {"status": "created", "webhook": webhook}


@router.delete("/outgoing/{webhook_id}")
async def delete_outgoing_webhook(webhook_id: int, user=Depends(get_current_user)):
    global _outgoing_webhooks
    _outgoing_webhooks = [w for w in _outgoing_webhooks if w.get("id") != webhook_id]
    return {"status": "deleted"}
