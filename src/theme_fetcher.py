#!/usr/bin/env python3
"""Theme selection from the 500-theme poetry catalogue with channel-wide
deduplication (a theme is never reused while it appears in video_history)."""

import json
import os
import random
from pathlib import Path

THEMES_PATH = Path(os.environ.get("POETRY_THEMES_PATH", "data/poetry_themes.json"))
HISTORY_PATH = Path(os.environ.get("VIDEO_HISTORY_PATH", "data/video_history.json"))


def _used_themes() -> set:
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(v.get("topic", "")).strip().lower() for v in history if v.get("topic")}


def get_theme(exclude_recent: int = 400) -> dict:
    catalogue = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    used = _used_themes()
    fresh = [t for t in catalogue if t["theme"].strip().lower() not in used]
    if not fresh:
        fresh = catalogue  # catalogue exhausted → restart (500 themes ≈ 166 days at 3/day)
    chosen = random.choice(fresh[-exclude_recent:] if len(fresh) > exclude_recent else fresh)
    return {"topic": chosen["theme"], "series_number": chosen.get("series_number"),
            "series_title": chosen.get("series_title"), "source": "poetry_series"}


if __name__ == "__main__":
    print(get_theme())
