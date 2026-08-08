#!/usr/bin/env python3
"""scripts/tune_schedule.py — ML self-tuning cron generator.

Reads the autonomous brain's learned best publish slots (data/autonomous_state.json)
and converts them into the GitHub Actions `schedule` crons the workflow should
run, writing data/recommended_schedule.json. This is how the ML "manages the
time/cron" itself: as slot performance changes, the recommended crons change.

Pipeline runs 30 min before each PKT publish peak (so the video is ready when
YouTube flips it public at the peak). PKT = UTC+5. A slot at H:00 PKT means the
pipeline should start at (H-1):30 PKT = (H-1-5):30 UTC.

Run inside daily-analytics.yml after autonomous_controller.analyse().
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("KHATEB_DATA_DIR", str(ROOT / "data")))
STATE = DATA / "autonomous_state.json"
OUT = DATA / "recommended_schedule.json"


def _to_cron(pkt_hour: int) -> str:
    """PKT peak hour -> cron (UTC) starting the pipeline 30 min before."""
    # Pipeline start (PKT) = peak - 30min
    start_pkt_h = (pkt_hour - 1) % 24
    start_pkt_m = 30
    # Convert to UTC (PKT = UTC+5)
    total_min = start_pkt_h * 60 + start_pkt_m - 5 * 60
    total_min %= 24 * 60
    utc_h, utc_m = divmod(total_min, 60)
    return f"{utc_m} {utc_h} * * *"


def main() -> int:
    if not STATE.exists():
        print("No autonomous_state.json — nothing to tune (first run).")
        return 0
    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)
    slots = state.get("best_publish_slots") or [int(x) for x in os.environ.get("PUBLISH_SLOTS", "10,14,21").split(",") if x.strip()]
    slots = [int(s) for s in slots if str(s).isdigit()]
    crons = [_to_cron(s) for s in sorted(slots)]

    payload = {
        "generated_at_utc": state.get("generated_at"),
        "best_publish_slots_pkt": slots,
        "recommended_crons_utc": crons,
        "explanation": "Pipeline runs 30 min before each learned PKT peak so the video "
                       "is scheduled to auto-publish exactly at the peak.",
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
