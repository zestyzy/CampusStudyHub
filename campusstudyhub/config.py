"""Configuration management for CampusStudyHub."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

DATA_DIR = Path("data")
CONFIG_PATH = DATA_DIR / "config.json"


@dataclass
class AppConfig:
    """Represents persisted configuration for the application."""

    base_directory: str
    courses: List[str]
    upcoming_window_days: int = 7

    @classmethod
    def default(cls) -> "AppConfig":
        """Return default configuration values."""
        home = Path.home()
        default_base = str(home / "CampusStudyMaterials")
        return cls(
            base_directory=default_base,
            courses=["Computer Science", "Mathematics", "Physics"],
            upcoming_window_days=7,
        )


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(exist_ok=True)


def load_config() -> AppConfig:
    """Load configuration from disk or create defaults."""
    ensure_data_dir()
    if not CONFIG_PATH.exists():
        cfg = AppConfig.default()
        save_config(cfg)
        return cfg

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return AppConfig(**raw)
    except Exception:
        # On error, fall back to defaults but do not overwrite existing file.
        return AppConfig.default()


def save_config(config: AppConfig) -> None:
    """Persist configuration to disk."""
    ensure_data_dir()
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)
