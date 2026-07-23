#!/usr/bin/env python3
"""Khateb-Ishq pipeline — Urdu sad-poetry Shorts, end to end.

Lean on purpose (fewer moving parts than the science channels):
  theme → Urdu poetry script (Groq) → AI images → Urdu edge-tts voice
  → video (RTL captions) → upload private + publishAt (PKT peaks) → history
"""

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("pipeline.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

from theme_fetcher import get_theme
from script_generator import generate_script
from image_generator import generate_scene_image
from voice_generator import generate_voice_segments
from video_editor import build_video, generate_thumbnail
from uploader import upload_all
from scheduler import PakistanPeakTimeScheduler

MAX_SCRIPT_ATTEMPTS = 3
MAX_IMAGE_RETRIES = 3
HISTORY_PATH = os.environ.get("VIDEO_HISTORY_PATH", "data/video_history.json")
TARGET_MIN = float(os.environ.get("TARGET_MIN_SECONDS", "30"))
TARGET_MAX = float(os.environ.get("TARGET_MAX_SECONDS", "57"))


def _load_history() -> list:
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(record: dict) -> None:
    history = _load_history() + [record]
    os.makedirs(os.path.dirname(HISTORY_PATH) or ".", exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(history[-540:], fh, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_PATH)


def _script_with_retries(theme: str) -> dict:
    for attempt in range(1, MAX_SCRIPT_ATTEMPTS + 1):
        try:
            script = generate_script(theme=theme)
            if script:
                return script
        except Exception as exc:
            logger.warning("Script attempt %d failed: %s", attempt, exc)
            time.sleep(5 * attempt)
    raise RuntimeError("All poetry-script attempts failed")


def run_pipeline(theme: str = None) -> dict:
    start = time.time()
    scheduler = PakistanPeakTimeScheduler()
    logger.info("=" * 60 + "\n🎙 KHATEB-ISHQ — URDU POETRY PIPELINE\n" + "=" * 60)

    # Anti-spam: minimum gap between posts (default 3h on this channel).
    history = _load_history()
    if history and history[-1].get("posted_at"):
        try:
            last_dt = datetime.fromisoformat(history[-1]["posted_at"])
            if not scheduler.validate_posting_interval(last_dt):
                if os.environ.get("ENFORCE_POSTING_GAP", "true").lower() == "true":
                    # LOUD skip: show a visible warning on the GitHub run summary
                    # so the owner immediately sees "no video THIS run, by design"
                    # instead of a quiet green run that produced nothing.
                    hrs = os.environ.get("MIN_POST_GAP_HOURS", "3.0")
                    print(f"::warning title=Skip (anti-spam, by design)::Last post was less than "
                          f"{hrs}h ago — this run made NO video on purpose. Roz ki 3 videos "
                          f"(10:00 / 14:00 / 21:00 PKT) apne time pe banti rahengi. "
                          f"Test ke liye 'Run workflow' pe force=true tick karein.")
                    logger.warning("Too soon since last post — skipping (ENFORCE_POSTING_GAP=true)")
                    return {"success": False, "skipped": "posting_interval"}
        except Exception as exc:
            logger.warning("Gap check failed (continuing): %s", exc)

    # 1. Theme + script
    theme_record = {"topic": theme} if theme else get_theme()
    logger.info("Theme: %s", theme_record["topic"])
    script = _script_with_retries(theme_record["topic"])
    script["topic"] = theme_record["topic"]
    script["series_title"] = theme_record.get("series_title") or script.get("title")
    logger.info("Script (%s / %s): %s", script.get("source"), script.get("poet"), script.get("title"))

    # 2. Images (deduped within the video)
    used_hashes, used_fallbacks = set(), set()
    image_paths, media_types = [], []
    for i, scene in enumerate(script["scenes"]):
        for attempt in range(MAX_IMAGE_RETRIES):
            result = generate_scene_image(i, scene, used_hashes, used_fallbacks)
            if result and os.path.exists(result["path"]):
                image_paths.append(result["path"])
                media_types.append("image")
                break
            if attempt == MAX_IMAGE_RETRIES - 1:
                raise RuntimeError(f"Image failed for scene {i+1}")
    logger.info("Images ready: %d scenes", len(image_paths))

    # 3. Urdu voice
    segments = generate_voice_segments(script["scenes"])
    narration = sum(s["duration"] for s in segments)
    if narration > TARGET_MAX * 1.15:
        raise RuntimeError(f"Narration too long ({narration:.1f}s > {TARGET_MAX}s) — regenerate shorter nazm")
    logger.info("Voice ready: %.1fs", narration)

    # 4. Video (+ thumbnail)
    final_video = build_video(image_paths, segments, script["scenes"])
    thumb = generate_thumbnail(image_paths[0], script.get("title") or "اردو شاعری")

    # 5. Upload (private → publishAt at PKT peak)
    result = upload_all(final_video, thumb, script)

    _save_history({
        "title": script.get("title"), "topic": script.get("topic"),
        "poet": script.get("poet"), "source": script.get("source"),
        "trend_source": "poetry_series",
        "voiceover": script.get("voiceover", "")[:500],
        "posted_at": datetime.now(timezone.utc).isoformat() if result.get("youtube_success") else None,
        "youtube_video_id": result.get("youtube_video_id"),
        "publish_at": result.get("publish_at"),
    })
    logger.info("✅ DONE in %.0fs — %s (%s)", time.time() - start,
                script.get("title"), result.get("youtube_video_id"))
    return {"success": True, "title": script.get("title"), "video_id": result.get("youtube_video_id")}


def main() -> None:
    try:
        topic = os.environ.get("VIDEO_TOPIC") or None
        run_pipeline(theme=topic)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as exc:
        logger.error("Pipeline failed: %s\n%s", exc, traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
