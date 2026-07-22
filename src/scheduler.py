#!/usr/bin/env python3
"""Pakistan-time peak scheduler (Asia/Karachi — no DST, beautifully simple)."""

import os
from datetime import datetime, timedelta

import pytz


class PakistanPeakTimeScheduler:
    """Poetry-audience peaks (PKT): 10:00 morning scroll, 14:00 lunch,
    21:00–23:00 the sad-poetry golden hours."""

    TIMEZONE = os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi")
    PEAK_TIMES = [
        {"hour": 10, "minute": 0, "name": "Morning"},
        {"hour": 14, "minute": 0, "name": "Lunch"},
        {"hour": 21, "minute": 0, "name": "Night poetry hours"},
    ]

    def __init__(self):
        self.local_tz = pytz.timezone(self.TIMEZONE)
        self.utc_tz = pytz.UTC

    def min_gap_hours(self) -> float:
        return float(os.environ.get("MIN_POST_GAP_HOURS", "3.0"))

    def validate_posting_interval(self, last_post_time: datetime) -> bool:
        if last_post_time.tzinfo is None:
            last_post_time = last_post_time.replace(tzinfo=pytz.UTC)
        elapsed_h = (datetime.now(self.local_tz) - last_post_time).total_seconds() / 3600
        return elapsed_h >= self.min_gap_hours()


def compute_publish_at(now: datetime = None) -> str:
    """Next peak slot (RFC-3339 UTC 'Z'), always >=30 min in the future.
    Honors env: PUBLISH_TIMEZONE, PUBLISH_SLOTS='10:00,14:00,21:00'."""
    tz = pytz.timezone(os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi"))
    slots = []
    for chunk in os.environ.get("PUBLISH_SLOTS", "10:00,14:00,21:00").split(","):
        hour, minute = chunk.strip().split(":")
        slots.append((int(hour), int(minute)))
    now_local = (now or datetime.now(tz)).astimezone(tz)
    candidates = []
    for day in (0, 1):
        for hour, minute in slots:
            slot = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day)
            if slot >= now_local + timedelta(minutes=30):
                candidates.append(slot)
    best = min(candidates) if candidates else (now_local + timedelta(days=1)).replace(
        hour=slots[0][0], minute=slots[0][1], second=0, microsecond=0)
    return best.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
