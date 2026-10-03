"""Nightly scheduler (FR-302), off by default via scheduler.enabled in config.yaml."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from backend.config import AppConfig

logger = logging.getLogger("gridsight.scheduler")
SYD = ZoneInfo("Australia/Sydney")


def build_scheduler(trigger: Callable[..., object], config: AppConfig) -> BackgroundScheduler | None:
    if not config.scheduler_enabled:
        return None

    def job() -> None:
        origin = datetime.now(SYD).replace(
            hour=config.scheduler_cron_hour, minute=0, second=0, microsecond=0
        )
        logger.info("scheduled nightly run for origin=%s", origin.isoformat())
        try:
            trigger(origin, force=True)
        except Exception:
            logger.exception("scheduled run failed")

    sched = BackgroundScheduler(timezone=SYD)
    sched.add_job(job, "cron", hour=config.scheduler_cron_hour, minute=0, id="gridsight-nightly", replace_existing=True)
    return sched
