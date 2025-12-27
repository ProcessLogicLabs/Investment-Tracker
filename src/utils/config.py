"""Configuration utilities for Asset Tracker."""

from pathlib import Path
from typing import Any, Dict
import json


class Config:
    """Application configuration manager."""

    DEFAULT_CONFIG = {
        'auto_update': True,
        'update_interval': 5,  # minutes
        'update_on_start': True,
        'show_charts': True,
        'confirm_delete': True,
        'window_width': 1200,
        'window_height': 700,
    }

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.json"
        self.config_path = config_path
        self._config = self.DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                    self._config.update(loaded)
            except Exception:
                pass  # Use defaults if file can't be read

    def save(self):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception:
            pass  # Silently fail if can't save

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value."""
        self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()
