import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.database import async_session
from app.models.schemas import UpdateLog

logger = logging.getLogger(__name__)

REPO_DIR = Path("/app")
COMPOSE_FILE = REPO_DIR / "docker-compose.yml"


class AutoUpdater:
    def __init__(self):
        self.current_version = self._get_current_version()
        self.is_updating = False

    def _get_current_version(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _get_current_tag(self) -> str:
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else self.current_version[:8]
        except Exception:
            return self.current_version[:8]

    async def check_for_updates(self) -> Optional[dict]:
        if self.is_updating:
            logger.info("Update already in progress, skipping check")
            return None

        if not settings.auto_update_enabled:
            return None

        try:
            result = subprocess.run(
                ["git", "fetch", "origin", settings.auto_update_branch],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=60
            )
            if result.returncode != 0:
                logger.error(f"Git fetch failed: {result.stderr}")
                return None

            result = subprocess.run(
                ["git", "rev-parse", f"origin/{settings.auto_update_branch}"],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=10
            )
            remote_hash = result.stdout.strip()

            if remote_hash == self.current_version:
                logger.debug("System is up to date")
                return None

            result = subprocess.run(
                ["git", "log", "--oneline", f"{self.current_version}..origin/{settings.auto_update_branch}"],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=10
            )
            changes = result.stdout.strip()

            return {
                "current": self.current_version[:8],
                "available": remote_hash[:8],
                "changes": changes,
                "full_hash": remote_hash,
            }
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    async def apply_update(self, target_hash: str) -> bool:
        if self.is_updating:
            return False

        self.is_updating = True
        old_version = self._get_current_tag()
        log_entry = None

        try:
            async with async_session() as session:
                log_entry = UpdateLog(
                    version_from=old_version,
                    version_to=target_hash[:8],
                    commit_hash=target_hash,
                    status="downloading",
                )
                session.add(log_entry)
                await session.commit()
                log_id = log_entry.id

            result = subprocess.run(
                ["git", "pull", "origin", settings.auto_update_branch],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=120
            )
            if result.returncode != 0:
                raise Exception(f"Git pull failed: {result.stderr}")

            await self._update_log(log_id, "building")

            result = subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "build", "--parallel"],
                capture_output=True, text=True, cwd=str(REPO_DIR), timeout=600
            )
            if result.returncode != 0:
                raise Exception(f"Docker build failed: {result.stderr}")

            await self._update_log(log_id, "restarting")

            logger.info(f"Update successful: {old_version} -> {target_hash[:8]}")
            logger.info(f"Restarting services in {settings.auto_update_restart_delay_seconds}s...")

            await self._update_log(log_id, "success", completed=True)

            asyncio.get_event_loop().call_later(
                settings.auto_update_restart_delay_seconds,
                lambda: subprocess.Popen(
                    ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--remove-orphans"],
                    cwd=str(REPO_DIR)
                )
            )

            self.current_version = target_hash
            return True

        except Exception as e:
            logger.error(f"Update failed: {e}")
            if log_entry:
                await self._update_log(log_entry.id, "failed", details=str(e), completed=True)

            try:
                subprocess.run(
                    ["git", "reset", "--hard", self.current_version],
                    capture_output=True, cwd=str(REPO_DIR), timeout=30
                )
            except Exception:
                pass

            return False
        finally:
            self.is_updating = False

    async def _update_log(self, log_id: int, status: str, details: str = None, completed: bool = False):
        try:
            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(UpdateLog).where(UpdateLog.id == log_id)
                log = (await session.execute(stmt)).scalar_one_or_none()
                if log:
                    log.status = status
                    if details:
                        log.details = details
                    if completed:
                        log.completed_at = datetime.utcnow()
                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update log: {e}")

    async def get_update_status(self) -> dict:
        return {
            "current_version": self._get_current_tag(),
            "current_hash": self.current_version[:8],
            "auto_update_enabled": settings.auto_update_enabled,
            "update_branch": settings.auto_update_branch,
            "is_updating": self.is_updating,
            "check_interval_minutes": settings.auto_update_check_interval_minutes,
        }


updater = AutoUpdater()
