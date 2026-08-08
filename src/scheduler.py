#!/usr/bin/env python3
"""Pakistan-time peak scheduler (Asia/Karachi — no DST, beautifully simple).

Updated with REAL channel analytics data — day-specific peak hours.
"""

import os
from datetime import datetime, timedelta

import pytz


class PakistanPeakTimeScheduler:
    """Channel-specific peak times based on REAL YouTube Analytics data.

    Owner provided (2026-08-01) — these are the ACTUAL active hours
    when the channel's audience is online, by day of the week:
    """

    TIMEZONE = os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi")

    # ── Real channel data — day-specific peak hours (PKT) ──────────────
    # Monday=0 ... Sunday=6
    DAY_PEAKS = {
        0: [15, 16],                          # Monday: 3pm, 4pm
        1: [15],                              # Tuesday: 3pm
        2: [15, 16, 17, 20, 22],              # Wednesday: 3,4,5,8,10pm
        3: [13, 16, 17, 20, 22],              # Thursday: 1,4,5,8,10pm
        4: [14, 15, 17, 20],                  # Friday: 2,3,5,8pm
        5: [15, 17, 23],                      # Saturday: 3,5,11pm
        6: [19, 22],                          # Sunday: 7pm, 10pm
    }

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

    def get_today_peaks(self, dt: datetime = None) -> list:
        """Get peak hours for a specific day (based on channel data)."""
        if dt is None:
            dt = datetime.now(self.local_tz)
        weekday = dt.weekday()  # 0=Monday ... 6=Sunday
        return self.DAY_PEAKS.get(weekday, [14, 21])

    def get_next_peak(self, now: datetime = None) -> datetime:
        """Find the next peak slot from now, checking today and tomorrow."""
        if now is None:
            now = datetime.now(self.local_tz)
        else:
            now = now.astimezone(self.local_tz)

        # Check today's peaks
        for hour in self.get_today_peaks(now):
            slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot >= now + timedelta(minutes=30):
                return slot

        # Check tomorrow's peaks
        tomorrow = now + timedelta(days=1)
        tomorrow_peaks = self.get_today_peaks(tomorrow)
        if tomorrow_peaks:
            return tomorrow.replace(hour=tomorrow_peaks[0], minute=0, second=0, microsecond=0)

        # Fallback
        return now + timedelta(hours=3)


def _taken_publish_times() -> set:
    """Read already-scheduled publishAt timestamps from upload_state.json and
    video_history.json so consecutive runs don't all claim the SAME peak slot
    (which used to publish 2-3 videos at once)."""
    import json as _json
    taken: set = set()
    paths = [
        os.environ.get("UPLOAD_STATE_PATH", "data/upload_state.json"),
        os.environ.get("VIDEO_HISTORY_PATH", "data/video_history.json"),
    ]
    for path in paths:
        try:
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                data = _json.load(fh)
            if isinstance(data, list):
                for rec in data:
                    if isinstance(rec, dict):
                        pa = rec.get("publish_at")
                        if pa:
                            taken.add(str(pa))
            elif isinstance(data, dict):
                for rec in data.values():
                    if isinstance(rec, dict) and rec.get("publish_at"):
                        taken.add(str(rec["publish_at"]))
        except Exception:
            pass
    return taken


def compute_publish_at(now: datetime = None) -> str:
    """Next peak slot (RFC-3339 UTC 'Z'), always >=30 min in the future.

    Uses REAL channel data for day-specific peak hours.
    Falls back to PUBLISH_SLOTS env var if set.
    """
    tz = pytz.timezone(os.environ.get("PUBLISH_TIMEZONE", "Asia/Karachi"))

    # Check if custom PUBLISH_SLOTS is set (override)
    custom_slots = os.environ.get("PUBLISH_SLOTS", "").strip()
    if custom_slots:
        slots = []
        for chunk in custom_slots.split(","):
            hour, minute = chunk.strip().split(":")
            slots.append((int(hour), int(minute)))
        now_local = (now or datetime.now(tz)).astimezone(tz)
        taken = _taken_publish_times()
        candidates = []
        for day in range(0, 3):
            for hour, minute in slots:
                slot = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day)
                if slot >= now_local + timedelta(minutes=30):
                    if slot.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") not in taken:
                        candidates.append(slot)
        best = min(candidates) if candidates else (now_local + timedelta(days=1)).replace(
            hour=slots[0][0], minute=slots[0][1], second=0, microsecond=0)
        return best.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Use REAL channel data ──
    scheduler = PakistanPeakTimeScheduler()
    now_local = (now or datetime.now(tz)).astimezone(tz)

    taken = _taken_publish_times()
    candidates = []
    # Look ahead across the next 4 days so consecutive runs land on distinct peaks.
    for day in range(0, 4):
        day_dt = now_local + timedelta(days=day)
        for hour in scheduler.get_today_peaks(day_dt):
            slot = day_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot >= now_local + timedelta(minutes=30):
                if slot.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") not in taken:
                    candidates.append(slot)
    best = min(candidates) if candidates else (now_local + timedelta(hours=3))
    return best.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
