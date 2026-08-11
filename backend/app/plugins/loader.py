import importlib
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class CollectorPlugin(Protocol):
    name: str
    category: str
    interval_seconds: int

    async def collect(self) -> list[dict]: ...


@runtime_checkable
class AnalyzerPlugin(Protocol):
    name: str

    async def analyze(self, data: dict) -> dict: ...


@runtime_checkable
class NotifierPlugin(Protocol):
    name: str

    async def notify(self, alert: dict) -> bool: ...


class PluginManager:
    def __init__(self):
        self.collectors: list[CollectorPlugin] = []
        self.analyzers: list[AnalyzerPlugin] = []
        self.notifiers: list[NotifierPlugin] = []

    def load_plugins(self, plugin_dir: str = None):
        if plugin_dir is None:
            plugin_dir = str(Path(__file__).parent / "installed")

        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            plugin_path.mkdir(parents=True, exist_ok=True)
            return

        for py_file in plugin_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                module_name = f"app.plugins.installed.{py_file.stem}"
                module = importlib.import_module(module_name)

                if hasattr(module, "collector") and isinstance(module.collector, CollectorPlugin):
                    self.collectors.append(module.collector)
                    logger.info(f"Loaded collector plugin: {module.collector.name}")

                if hasattr(module, "analyzer") and isinstance(module.analyzer, AnalyzerPlugin):
                    self.analyzers.append(module.analyzer)
                    logger.info(f"Loaded analyzer plugin: {module.analyzer.name}")

                if hasattr(module, "notifier") and isinstance(module.notifier, NotifierPlugin):
                    self.notifiers.append(module.notifier)
                    logger.info(f"Loaded notifier plugin: {module.notifier.name}")

            except Exception as e:
                logger.error(f"Failed to load plugin {py_file.name}: {e}")

    def get_collectors(self) -> list[CollectorPlugin]:
        return self.collectors

    def get_analyzers(self) -> list[AnalyzerPlugin]:
        return self.analyzers

    def get_notifiers(self) -> list[NotifierPlugin]:
        return self.notifiers


plugin_manager = PluginManager()
