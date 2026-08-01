#!/usr/bin/env python3
"""Khateb-Ishq ADVANCED pipeline — Urdu sad-poetry Shorts, end to end.

Enhanced version with:
  ✅ Smart Theme Selector (performance-learned + trend-predicted)
  ✅ Hashtag Optimizer (YouTube search trends + competitor analysis)
  ✅ Trend Predictor (autosuggest + seasonal + cultural events)
  ✅ Performance Learner (viral pattern detection → smarter themes)
  ✅ Multi-Platform Poster (TikTok, Instagram Reels, Facebook Reels)
  ✅ Engagement Bot (auto-comments, replies, community posts)

Pipeline flow:
  1. Refresh performance data (if stale)
  2. Select theme via smart selector
  3. Generate Urdu poetry script (Groq/Gemini)
  4. Generate AI images (9-provider fallback)
  5. Generate Urdu voice (Edge-TTS/ElevenLabs/Clone)
  6. Build video (RTL captions, Ken-Burns, fast-cut, grading)
  7. Optimize hashtags (trend-based)
  8. Upload to YouTube (private → publishAt at PKT peaks)
  9. Post engagement comment + pin
  10. Cross-post to other platforms (if enabled)
  11. Save performance data
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
logger = logging.getLogger("khateb-ishq-advanced")

# ── Core imports (from existing project) ───────────────────────────────────
from smart_theme_selector import SmartThemeSelector
from script_generator import generate_script
from image_generator import generate_scene_image
from voice_generator import generate_voice_segments
from video_editor import build_video, generate_thumbnail
from uploader import upload_all
from scheduler import PakistanPeakTimeScheduler

# ── Advanced imports ───────────────────────────────────────────────────────
from performance_learner import PerformanceLearner
from hashtag_optimizer import HashtagOptimizer
from engagement_bot import EngagementBot

MAX_SCRIPT_ATTEMPTS = 3
MAX_IMAGE_RETRIES = 3
HISTORY_PATH = os.environ.get("VIDEO_HISTORY_PATH", "data/video_history.json")
TARGET_MIN = float(os.environ.get("TARGET_MIN_SECONDS", "40"))
TARGET_MAX = float(os.environ.get("TARGET_MAX_SECONDS", "57"))

# How often to refresh performance data (hours)
PERF_REFRESH_HOURS = float(os.environ.get("PERF_REFRESH_HOURS", "24"))


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


def _should_refresh_performance() -> bool:
    """Check if performance data is stale and needs refreshing."""
    perf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "data", "performance_profile.json")
    try:
        with open(perf_path, encoding="utf-8") as fh:
            data = json.load(fh)
            last_updated = data.get("last_updated")
            if not last_updated:
                return True
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last_updated)).total_seconds() / 3600
            return elapsed >= PERF_REFRESH_HOURS
    except (OSError, json.JSONDecodeError):
        return True


def run_pipeline(theme: str = None) -> dict:
    """Run the ADVANCED Khateb-Ishq pipeline."""
    start = time.time()
    scheduler = PakistanPeakTimeScheduler()

    logger.info("=" * 60 + "\n🎙 KHATEB-ISHQ ADVANCED — URDU POETRY PIPELINE\n" + "=" * 60)

    # ── Step 0: Refresh performance data (if stale) ────────────────────────
    if _should_refresh_performance():
        logger.info("📊 Refreshing performance data...")
        try:
            learner = PerformanceLearner()
            learner.refresh_stats()
            logger.info("✅ Performance data refreshed")
        except Exception as exc:
            logger.warning("Performance refresh failed (non-critical): %s", exc)
    else:
        logger.info("📊 Performance data is fresh, skipping refresh")

    # ── Step 0.5: Anti-spam check ─────────────────────────────────────────
    history = _load_history()
    if history and history[-1].get("posted_at"):
        try:
            last_dt = datetime.fromisoformat(history[-1]["posted_at"])
            if not scheduler.validate_posting_interval(last_dt):
                if os.environ.get("ENFORCE_POSTING_GAP", "true").lower() == "true":
                    hrs = os.environ.get("MIN_POST_GAP_HOURS", "3.0")
                    print(f"::warning title=Skip (anti-spam, by design)::Last post was less than "
                          f"{hrs}h ago — this run made NO video on purpose.")
                    logger.warning("Too soon since last post — skipping (ENFORCE_POSTING_GAP=true)")
                    return {"success": False, "skipped": "posting_interval"}
        except Exception as exc:
            logger.warning("Gap check failed (continuing): %s", exc)

    # ── Step 1: Smart Theme Selection ──────────────────────────────────────
    theme_selector = SmartThemeSelector()
    if theme:
        theme_record = {"topic": theme, "series_title": f"Kalam #1: {theme[:30]}", "source": "manual"}
    else:
        theme_record = theme_selector.select()
    logger.info("🎯 Theme: %s (strategy: %s, source: %s)",
                theme_record["topic"],
                theme_record.get("strategy", "unknown"),
                theme_record.get("source", "unknown"))

    # ── Step 2: Script Generation ──────────────────────────────────────────
    script = _script_with_retries(theme_record["topic"])
    script["topic"] = theme_record["topic"]
    script["series_title"] = theme_record.get("series_title") or script.get("title")
    script["theme_strategy"] = theme_record.get("strategy", "unknown")
    logger.info("📝 Script (%s / %s): %s", script.get("source"), script.get("poet"), script.get("title"))

    # ── Step 3: Image Generation (deduped within video) ────────────────────
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
    logger.info("🖼️ Images ready: %d scenes", len(image_paths))

    # ── Step 4: Voice Generation ───────────────────────────────────────────
    segments = generate_voice_segments(script["scenes"])
    narration = sum(s["duration"] for s in segments)
    if narration > TARGET_MAX * 1.15:
        raise RuntimeError(f"Narration too long ({narration:.1f}s > {TARGET_MAX}s) — regenerate shorter nazm")
    logger.info("🎙️ Voice ready: %.1fs", narration)

    # ── Step 5: Video Build + Thumbnail ────────────────────────────────────
    final_video = build_video(image_paths, segments, script["scenes"])

    # ── Step 5.2: Add EMOTION to the video (heartbeat + rain + soul) ──
    try:
        from emotion_engine import add_emotion_to_video
        final_video = add_emotion_to_video(
            final_video, script["scenes"], emotion_level="high"
        )
        logger.info("💕 Emotion engine applied: heartbeat + rain + soul")
    except Exception as exc:
        logger.warning("Emotion engine failed (non-critical): %s", exc)

    # ── Step 5.5: Thumbnail A/B Testing ────────────────────────────────────
    try:
        from thumbnail_ab import ThumbnailABGenerator
        thumb_gen = ThumbnailABGenerator()
        hook_roman = (script.get("hook_roman") or
                      (script["scenes"][0].get("hook_roman") if script.get("scenes") else "") or
                      (script["scenes"][0].get("caption_roman") if script.get("scenes") else "") or "")
        title_display = script.get("title_roman") or script.get("title") or "Sad Urdu Poetry"
        thumb_variants = thumb_gen.generate_variants(
            image_paths[0], title_display, hook_roman)
        thumb = thumb_gen.select_best(thumb_variants)
        logger.info("🖼️ Thumbnail A/B: %d variants generated, best: %s",
                    len(thumb_variants), thumb)
    except Exception as exc:
        logger.warning("Thumbnail A/B failed (non-critical): %s — using basic thumbnail", exc)
        try:
            thumb = generate_thumbnail(image_paths[0], script.get("title") or "اردو شاعری")
        except Exception as exc2:
            logger.warning("Basic thumbnail also failed: %s — using first image", exc2)
            thumb = image_paths[0]
    logger.info("🎬 Video built: %s", final_video)

    # ── Step 6: Hashtag Optimization ───────────────────────────────────────
    try:
        hashtag_opt = HashtagOptimizer()
        optimized_tags = hashtag_opt.optimize(script_data=script)
        script["optimized_tags"] = optimized_tags
        logger.info("🏷️ Optimized %d hashtags: %s", len(optimized_tags),
                    ", ".join(f"#{t}" for t in optimized_tags[:5]))
    except Exception as exc:
        logger.warning("Hashtag optimization failed (non-critical): %s", exc)
        script["optimized_tags"] = script.get("tags", [])

    # ── Step 6.5: SEO Score Check ─────────────────────────────────────────
    try:
        from seo_scorer import SEOScorer
        scorer = SEOScorer()
        script = scorer.auto_fix(script)  # Auto-fix SEO issues
        seo_score = script.get("seo_score", {})
        if seo_score:
            logger.info("📊 SEO Score: %d/100 (Grade: %s) — %d fixes applied",
                        seo_score.get("total", 0), seo_score.get("grade", "?"),
                        seo_score.get("fix_count", 0))
            if not seo_score.get("passed", False):
                logger.warning("⚠️ SEO score below 70 — video may not rank well in search")
    except Exception as exc:
        logger.warning("SEO scoring failed (non-critical): %s", exc)

    # ── Step 7: YouTube Upload ─────────────────────────────────────────────
    result = upload_all(final_video, thumb, script)
    video_id = result.get("youtube_video_id")
    logger.info("📤 YouTube upload: %s", video_id or "FAILED")

    # ── Step 7.5: SRT Subtitles ────────────────────────────────────────────
    if video_id and result.get("youtube_success"):
        try:
            from srt_generator import generate_srt
            srt_path = generate_srt(segments, script["scenes"],
                                    output_path="output/subtitles.srt")
            logger.info("📝 SRT subtitles generated: %s", srt_path)
            # Note: YouTube API doesn't support SRT upload via API v3.
            # SRT is saved for manual upload or future API support.
        except Exception as exc:
            logger.warning("SRT generation failed (non-critical): %s", exc)

      # ── Step 8: Engagement Bot ─────────────────────────────────────────────
    if video_id and result.get("youtube_success"):
        try:
            bot = EngagementBot()
            # Post engagement question as pinned comment
            eng_result = bot.post_engagement_comment(video_id)
            if eng_result.get("success"):
                logger.info("💬 Engagement comment posted & pinned")
            # Generate community post content
            community_text = bot.generate_engagement_post(script)
            bot.post_community_post(community_text)
            logger.info("📢 Community post saved for manual posting")
        except Exception as exc:
            logger.warning("Engagement bot failed (non-critical): %s", exc)

        # ── Step 8.5: AI Comment Responder ─────────────────────────────────
        try:
            from ai_comment_responder import AICommentResponder
            responder = AICommentResponder()
            reply_result = responder.process_video_comments(video_id, max_replies=3)
            logger.info("🤖 AI replies: %d posted", reply_result.get("replies_posted", 0))
        except Exception as exc:
            logger.warning("AI comment responder failed (non-critical): %s", exc)

    # ── Step 9: Multi-Platform Posting ─────────────────────────────────────
    if video_id and result.get("youtube_success"):
        try:
            from multi_platform import MultiPlatformPoster
            poster = MultiPlatformPoster()
            if poster.enabled_platforms:
                mp_result = poster.post_all(final_video, script)
                logger.info("📱 Multi-platform: %s", mp_result.get("message", ""))
            else:
                logger.info("📱 Multi-platform: YouTube-only mode (no other platforms configured)")
        except Exception as exc:
            logger.warning("Multi-platform posting failed (non-critical): %s", exc)

    # ── Step 10: Save History ──────────────────────────────────────────────
    _save_history({
        "title": script.get("title"),
        "topic": script.get("topic"),
        "poet": script.get("poet"),
        "source": script.get("source"),
        "theme_strategy": theme_record.get("strategy", "unknown"),
        "trend_source": theme_record.get("source", "unknown"),
        "voiceover": script.get("voiceover", "")[:500],
        "optimized_tags": script.get("optimized_tags", []),
        "posted_at": datetime.now(timezone.utc).isoformat() if result.get("youtube_success") else None,
        "youtube_video_id": video_id,
        "publish_at": result.get("publish_at"),
    })

    elapsed = time.time() - start
    logger.info("✅ DONE in %.0fs — %s (%s) [strategy: %s]",
                elapsed, script.get("title"), video_id,
                theme_record.get("strategy", "unknown"))

    return {
        "success": True,
        "title": script.get("title"),
        "video_id": video_id,
        "theme_strategy": theme_record.get("strategy"),
    }


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
