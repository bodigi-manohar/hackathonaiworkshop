"""Backend settings: environment (.env) + config.yaml. All paths relative to project root."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "gridsight-backend"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    runs_dir: Path = PROJECT_ROOT / "runs"
    sample_dir: Path = PROJECT_ROOT / "contracts" / "sample"
    config_path: Path = BASE_DIR / "config.yaml"
    db_path: Path = BASE_DIR / "gridsight.db"

    run_cycle_timeout_seconds: int = 300
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    alert_webhook_url: str | None = Field(default=None, alias="ALERT_WEBHOOK_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o for o in (x.strip() for x in self.cors_origins.split(",")) if o]


@lru_cache
def get_settings() -> Settings:
    return Settings()


class AppConfig:
    """Typed view over backend/config.yaml (thresholds, tariff, battery, control)."""

    def __init__(self, data: dict):
        a = data.get("alerts", {})
        self.peak_threshold_kw: float = a.get("peak_threshold_kw", 170.0)
        self.peak_quantile: str = a.get("peak_quantile", "p50")
        self.critical_factor: float = a.get("critical_factor", 1.10)
        self.ramp_kw: float = a.get("ramp_kw", 20.0)
        self.ramp_window_slots: int = a.get("ramp_window_slots", 4)
        self.low_confidence_band_fraction: float = a.get("low_confidence_band_fraction", 0.25)
        self.drift_ratio_threshold: float = a.get("drift_ratio_threshold", 1.3)
        self.heatwave_apparent_temp_c: float = a.get("heatwave_apparent_temp_c", 33.0)
        self.cooldown_hours: float = a.get("cooldown_hours", 6.0)

        self.tariff: dict = data.get("tariff", {})
        self.battery: dict = data.get("battery", {})
        self.shiftable_loads: list[dict] = data.get("shiftable_loads", [])
        self.generator: dict = data.get("generator", {})

        c = data.get("control", {})
        self.control_enabled: bool = c.get("enabled", False)
        self.control_dry_run: bool = c.get("dry_run", True)
        self.control_max_kw: float = c.get("max_kw", 12.0)
        self.control_max_setpoint_change_kw: float = c.get("max_setpoint_change_kw", 5.0)

        s = data.get("scheduler", {})
        self.scheduler_enabled: bool = s.get("enabled", False)
        self.scheduler_cron_hour: int = s.get("cron_hour", 0)


@lru_cache
def get_app_config() -> AppConfig:
    path = Path(__file__).resolve().parent / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return AppConfig(yaml.safe_load(f) or {})


def reset_caches() -> None:
    get_settings.cache_clear()
    get_app_config.cache_clear()
