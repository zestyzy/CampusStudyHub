"""Configuration management for CampusStudyHub."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List

from .models import LanTarget

DATA_DIR = Path("data")
CONFIG_PATH = DATA_DIR / "config.json"


@dataclass
class AppConfig:
    """Represents persisted configuration for the application."""

    base_directory: str
    courses: List[str]
    upcoming_window_days: int = 7
    conference_window_days: int = 30
    lan_targets: List[LanTarget] = field(default_factory=list)
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_sender: str = "campusstudyhub@example.com"
    conference_sources: List[str] = field(default_factory=list)

    @classmethod
    def default(cls) -> "AppConfig":
        """Return default configuration values."""
        home = Path.home()
        default_base = str(home / "CampusStudyMaterials")
        return cls(
            base_directory=_normalize_base_directory(default_base),
            courses=["Computer Science", "Mathematics", "Physics"],
            upcoming_window_days=7,
            conference_window_days=30,
            lan_targets=[LanTarget(label="Localhost (example)", host="127.0.0.1", port=5055, email="")],
            smtp_host="localhost",
            smtp_port=25,
            smtp_sender="campusstudyhub@example.com",
            conference_sources=[
                "https://dblp.org/search/publ/rss?q=CCF+A+deadline",
                "https://eventseer.net/rss/cs",
            ],
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
        return _config_from_dict(raw)
    except Exception:
        # On error, fall back to defaults but do not overwrite existing file.
        return AppConfig.default()


def save_config(config: AppConfig) -> None:
    """Persist configuration to disk."""
    ensure_data_dir()
    config.base_directory = _normalize_base_directory(config.base_directory)
    serializable = asdict(config)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def _config_from_dict(raw: dict) -> AppConfig:
    """Safely build AppConfig from a dict, tolerating missing keys."""

    lan_targets_raw = raw.get("lan_targets", []) or []
    lan_targets = []
    for item in lan_targets_raw:
        try:
            lan_targets.append(LanTarget(**item))
        except TypeError:
            continue

    return AppConfig(
        base_directory=_normalize_base_directory(
            raw.get("base_directory", AppConfig.default().base_directory)
        ),
        courses=raw.get("courses", AppConfig.default().courses),
        upcoming_window_days=raw.get("upcoming_window_days", 7),
        conference_window_days=raw.get("conference_window_days", 30),
        lan_targets=lan_targets or AppConfig.default().lan_targets,
        smtp_host=raw.get("smtp_host", "localhost"),
        smtp_port=raw.get("smtp_port", 25),
        smtp_sender=raw.get("smtp_sender", "campusstudyhub@example.com"),
        conference_sources=raw.get("conference_sources", AppConfig.default().conference_sources),
    )


def _normalize_base_directory(path_str: str) -> str:
    """Return a user-expanded base directory string without requiring it to exist."""

    try:
        return str(Path(path_str).expanduser())
    except Exception:
        return path_str
