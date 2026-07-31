#!/usr/bin/env python3
"""Pakistan-time peak scheduler (Asia/Karachi — no DST, beautifully simple)."""

import os
from datetime import datetime, timedelta

import pytz


class PakistanPeakTimeScheduler:
    """South Asia Poetry-audience peaks (Pakistan/India):
    14:00 Afternoon Peak (Lunch/College-end),
    18:30 Evening Peak (Commute/Relaxation),
    21:30 Night Poetry Golden Hour (Absolute peak for sad poetry)."""

    TIMEZONE = os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi")
    PEAK_TIMES = [
        {"hour": 14, "minute": 0, "name": "Afternoon Peak (14:00 PKT / 14:30 IST)"},
        {"hour": 18, "minute": 30, "name": "Evening Peak (18:30 PKT / 19:00 IST)"},
        {"hour": 21, "minute": 30, "name": "Night Poetry Golden Hour (21:30 PKT / 22:00 IST)"},
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
    Honors env: PUBLISH_TIMEZONE, PUBLISH_SLOTS='14:00,18:30,21:30'."""
    tz = pytz.timezone(os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi"))
    slots = []
    for chunk in os.environ.get("PUBLISH_SLOTS", "14:00,18:30,21:30").split(","):
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
