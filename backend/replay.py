"""Replay helper: run N consecutive days through POST /run logic.

Usage: python -m backend.replay --start 2013-02-10 --days 7
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.config import get_app_config, get_settings
from backend.core.exceptions import RunError
from backend.db.session import SessionLocal, init_db
from backend.services.run_service import RunService
from backend.services.run_store import RunStore

SYD = ZoneInfo("Australia/Sydney")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay consecutive forecast cycles")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2013-02-10 (Australia/Sydney)")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    init_db()
    settings = get_settings()
    config = get_app_config()
    store = RunStore(settings)
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=SYD)

    failures = 0
    for i in range(args.days):
        origin = start + timedelta(days=i)
        db = SessionLocal()
        try:
            out = RunService(settings, config, store, db).trigger(origin)
            suffix = " (existing)" if out.already_existed else ""
            print(f"[{i + 1}/{args.days}] {origin:%Y-%m-%d} -> run {out.run_id}{suffix}")
        except RunError as e:
            failures += 1
            print(f"[{i + 1}/{args.days}] {origin:%Y-%m-%d} FAILED: {e}")
        finally:
            db.close()

    print(f"Done: {args.days - failures}/{args.days} runs succeeded.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
