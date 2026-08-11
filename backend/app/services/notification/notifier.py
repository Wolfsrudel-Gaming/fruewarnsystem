import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.schemas import Alert

logger = logging.getLogger(__name__)


async def send_alert_notifications(alert: Alert):
    channels = _get_channels_for_level(alert.escalation_level)
    sent = []

    for channel in channels:
        try:
            if channel == "push" and settings.ntfy_topic:
                await _send_ntfy(alert)
                sent.append("ntfy")
            elif channel == "telegram" and settings.telegram_bot_token:
                await _send_telegram(alert)
                sent.append("telegram")
            elif channel == "sms" and settings.twilio_account_sid:
                await _send_sms(alert)
                sent.append("sms")
            elif channel == "email" and settings.smtp_host:
                await _send_email(alert)
                sent.append("email")
        except Exception as e:
            logger.error(f"Failed to send {channel} notification: {e}")

    return sent


def _get_channels_for_level(level: int) -> list:
    if level >= 4:
        return ["push", "telegram", "sms", "email"]
    elif level >= 3:
        return ["push", "telegram", "sms"]
    elif level >= 2:
        return ["push", "telegram"]
    else:
        return ["push"]


def _format_alert_message(alert: Alert) -> str:
    severity_emoji = "🔴" if alert.score >= 70 else "🟠" if alert.score >= 40 else "🟡"
    return (
        f"{severity_emoji} DRK Frühwarnung\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 {alert.title}\n"
        f"📊 Score: {alert.score:.0f}/100\n"
        f"📝 {alert.description}\n"
        f"🕐 {alert.triggered_at.strftime('%d.%m.%Y %H:%M') if alert.triggered_at else 'jetzt'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )


async def _send_ntfy(alert: Alert):
    priority = "5" if alert.score >= 80 else "4" if alert.score >= 50 else "3"
    tags = "rotating_light" if alert.score >= 70 else "warning"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.ntfy_server}/{settings.ntfy_topic}",
            content=_format_alert_message(alert),
            headers={
                "Title": f"DRK Frühwarnung: {alert.category.value}",
                "Priority": priority,
                "Tags": tags,
            },
            timeout=10,
        )
    logger.info(f"ntfy notification sent for alert {alert.id}")


async def _send_telegram(alert: Alert):
    message = _format_alert_message(alert)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    targets = []
    if settings.telegram_chat_id:
        targets.append(settings.telegram_chat_id)
    if settings.telegram_group_id:
        targets.append(settings.telegram_group_id)

    async with httpx.AsyncClient() as client:
        for chat_id in targets:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)

    logger.info(f"Telegram notification sent for alert {alert.id}")


async def _send_sms(alert: Alert):
    if not all([settings.twilio_account_sid, settings.twilio_auth_token,
                settings.twilio_from_number, settings.alert_phone_number]):
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    message = f"DRK ALARM: {alert.title} - Score {alert.score:.0f}/100"

    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            data={
                "To": settings.alert_phone_number,
                "From": settings.twilio_from_number,
                "Body": message[:160],
            },
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=10,
        )
    logger.info(f"SMS notification sent for alert {alert.id}")


async def _send_email(alert: Alert):
    import smtplib
    from email.mime.text import MIMEText

    if not all([settings.smtp_host, settings.smtp_user, settings.alert_email]):
        return

    msg = MIMEText(_format_alert_message(alert))
    msg["Subject"] = f"DRK Frühwarnung: {alert.title}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.alert_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)

    logger.info(f"Email notification sent for alert {alert.id}")


async def send_daily_report(scores: dict):
    report = _format_daily_report(scores)

    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(url, json={
                    "chat_id": settings.telegram_chat_id,
                    "text": report,
                }, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send daily report via Telegram: {e}")

    if settings.smtp_host and settings.alert_email:
        try:
            await _send_email_report(report)
        except Exception as e:
            logger.error(f"Failed to send daily report via email: {e}")


def _format_daily_report(scores: dict) -> str:
    overall = scores.get("overall", {}).get("score", 0)
    emoji = "🟢" if overall < 20 else "🟡" if overall < 40 else "🟠" if overall < 70 else "🔴"

    lines = [
        f"📊 DRK Troisdorf - Täglicher Lagebericht",
        f"📅 {datetime.utcnow().strftime('%d.%m.%Y')}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"{emoji} Gesamtrisiko: {overall:.0f}/100",
        f"",
    ]

    category_names = {
        "water": "🌊 Hochwasser",
        "weather": "⛈️ Wetter",
        "fire": "🔥 Waldbrand",
        "air_quality": "💨 Luftqualität",
        "traffic": "🚗 Verkehr",
        "official_warning": "⚠️ Behördenwarnungen",
        "news": "📰 Nachrichten",
    }

    for key, name in category_names.items():
        if key in scores:
            s = scores[key]
            score_bar = _score_bar(s["score"])
            lines.append(f"{name}: {score_bar} {s['score']:.0f}")
            if s.get("detail"):
                lines.append(f"   └ {s['detail']}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _score_bar(score: float) -> str:
    filled = int(score / 10)
    return "█" * filled + "░" * (10 - filled)


async def _send_email_report(report: str):
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(report)
    msg["Subject"] = f"DRK Lagebericht {datetime.utcnow().strftime('%d.%m.%Y')}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.alert_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
