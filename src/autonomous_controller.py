"""autonomous_controller.py — Khateb-Ishq's fully autonomous ML brain.

A-to-Z decision engine. It aggregates EVERY learnable signal — CTR, retention,
video quality, engagement, traffic source, past mistakes, cadence, publish
slots — and turns them into ENFORCED decisions the pipeline MUST obey, not
recommendations a human has to act on.

Everything the brain decides is written to data/autonomous_state.json so the
whole decision log is auditable, and exposed via get_controls() so the pipeline
(cadence, theme selector, scheduler, quality gate) can read it at runtime.

Decision surface (all auto):
  * recommended_cadence        -> how many uploads/day (bounded 1..3)
  * best_publish_slots         -> which PKT peaks to schedule on
  * winning_themes / poets     -> proven performers get priority
  * flop_themes / flop_poets   -> proven failures get blocked
  * best_caption_style / best_voice -> creative preferences
  * traffic_source_insight     -> where viewers come from (YT Analytics)
  * engagement_rate            -> avg comments per video
  * quality_gate               -> min quality score a video must pass
  * known_mistakes             -> recurring failures (garbled Urdu etc.)
  * throttle                   -> slow down when recent videos flopped
  * quality_issues             -> per-video quality audit

Design rule: never act on a single sample. Winners/flops need >= WINNER_MIN
samples before they move a weight. Small samples produce confident nonsense.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("autonomous_controller")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("KHATEB_DATA_DIR", str(ROOT / "data")))

AUTONOMOUS_STATE_PATH = os.environ.get(
    "AUTONOMOUS_STATE_PATH", str(DATA_DIR / "autonomous_state.json")
)
VIDEO_HISTORY_PATH = os.environ.get("VIDEO_HISTORY_PATH", str(DATA_DIR / "video_history.json"))
PERFORMANCE_PROFILE_PATH = str(DATA_DIR / "performance_profile.json")
TREND_PREDICTIONS_PATH = str(DATA_DIR / "trend_predictions.json")

MIN_SAMPLES = int(os.environ.get("AUTO_MIN_SAMPLES", "1"))
WINNER_MIN_SAMPLES = int(os.environ.get("AUTO_WINNER_MIN", "2"))
FLOP_VIEWS = int(os.environ.get("AUTO_FLOP_VIEWS", "300"))
WINNER_VIEWS = int(os.environ.get("AUTO_WINNER_VIEWS", "5000"))
THROTTLE_VIEWS = int(os.environ.get("AUTO_THROTTLE_VIEWS", "500"))
THROTTLE_WINDOW = int(os.environ.get("AUTO_THROTTLE_WINDOW", "5"))
MIN_QUALITY_SCORE = int(os.environ.get("AUTO_MIN_QUALITY", "70"))
MAX_CADENCE = int(os.environ.get("AUTO_MAX_CADENCE", "3"))


def _load_json(path: str, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, payload) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as exc:
        logger.warning("Could not save autonomous state: %s", exc)


def _hours_since(iso: str) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return None


def _entry_views(entry: dict) -> int | None:
    """Real view count, or None if analytics hasn't been fetched yet.

    CRITICAL: absence of data must NOT be read as 0 views. New videos (uploaded
    <24-48h ago, or a channel whose YouTube analytics sync is not running) often
    have no fetched views yet. Treating them as 0 made the brain believe the
    channel was flopping (e.g. "last 4 videos avg 0 views") and throttled
    publishing, even though the Shorts had real views.
    """
    raw = entry.get("views")
    if raw is None:
        nested = entry.get("youtube_shorts") or entry.get("youtube") or {}
        raw = nested.get("views")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _detect_quality_issues(entry: dict) -> list[str]:
    """Audit a single video for known quality/mistake issues."""
    issues: list[str] = []
    title = entry.get("title", "") or ""
    voiceover = entry.get("voiceover", "") or ""
    for label, text in (("title", title), ("voiceover", voiceover)):
        if not text:
            continue
        urdu = len(re.findall(r"[\u0600-\u06FF]", text))
        total = len(text)
        if total and urdu / total < 0.3:
            issues.append(f"{label}: possibly garbled/non-Urdu text")
    if len(title) < 5:
        issues.append("title too short")
    if not voiceover or len(voiceover) < 30:
        issues.append("voiceover missing/too short")
    return issues


URDU_HOOK_PATTERNS = {
    "question": ["کیا", "کیوں", "کب", "کس", "کہاں", "کیا آپ"],
    "emotion": ["غم", "درد", "تڑپ", "یاد", "اشک", "دل", "آنسو", "جدائی"],
    "curiosity": ["راز", "حقیقت", "سچ", "چھپا", "پوشیدہ"],
}
STOP_URDU = {"اور", "کا", "کی", "کے", "میں", "ہے", "ہیں", "تھا", "تھی", "یہ", "وہ", "سے", "نہیں", "بھی"}


def _tokens_urdu(text: str) -> list[str]:
    import re as _re
    return _re.findall(r"[\u0600-\u06FF]+", text or "")


def _hook_score(script: dict) -> int:
    """Score how strong the opening hook is (0-100) from the hook/first scene."""
    text = (script.get("hook") or script.get("voiceover") or "")[:200]
    words = _tokens_urdu(text)
    if not words:
        return 40  # neutral when unknown
    score = 50
    low = text.lower()
    for pattern, kws in URDU_HOOK_PATTERNS.items():
        if any(k in low for k in kws):
            score += 15
    if len(words) >= 3:
        score += 10
    if len(words) > 15:
        score -= 10  # too long a hook loses attention
    return max(10, min(100, score))


def _topic_demand(topic: str, trends: dict) -> float:
    """Combine trend score (if any) with a base, for prioritizing topics."""
    if not topic:
        return 0.0
    t = topic.strip().lower()
    trend = trends.get("trending", {}) or {}
    for rec in (trend if isinstance(trend, list) else trend.get("topics", [])):
        if isinstance(rec, dict) and t in str(rec.get("topic", "")).lower():
            return float(rec.get("score", 50))
    return 50.0


def _estimate_ctr(entry: dict) -> float | None:
    """Estimate CTR from known fields if views/impressions present."""
    views = int(entry.get("views") or 0)
    imps = int(entry.get("impressions") or 0)
    if views and imps:
        return round(views / imps * 100.0, 2)
    return None


def _estimate_engagement(entry: dict) -> float | None:
    views = int(entry.get("views") or 0)
    comments = int(entry.get("comments") or 0)
    if views and comments:
        return round(comments / views * 100.0, 2)
    return None


def _learned_slots(slot_views: dict) -> list[int]:
    """Rank publish hours by avg views; return the top 3 PKT hours, falling
    back to the env PUBLISH_SLOTS if there is no view data yet."""
    buckets = []
    for hour, vals in slot_views.items():
        if any(vals):
            buckets.append((int(hour), len(vals), sum(vals) / len(vals)))
    if buckets:
        buckets.sort(key=lambda x: x[2], reverse=True)
        top = [b[0] for b in buckets[:3]]
        return top
    default = os.environ.get("PUBLISH_SLOTS", "10,14,21")
    return [int(x) for x in default.split(",") if x.strip()]


def _hook_style(script: dict) -> str:
    """Classify hook style: question / emotion / curiosity / neutral."""
    text = (script.get("hook") or script.get("voiceover") or "")[:200]
    low = text.lower()
    if any(k in low for k in URDU_HOOK_PATTERNS["question"]):
        return "question"
    if any(k in low for k in URDU_HOOK_PATTERNS["emotion"]):
        return "emotion"
    if any(k in low for k in URDU_HOOK_PATTERNS["curiosity"]):
        return "curiosity"
    return "neutral"


def analyse() -> dict:
    history = _load_json(VIDEO_HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    perf = _load_json(PERFORMANCE_PROFILE_PATH, {}) or {}

    theme_views: dict[str, list] = defaultdict(list)
    poet_views: dict[str, list] = defaultdict(list)
    cap_views: dict[str, list] = defaultdict(list)
    voice_views: dict[str, list] = defaultdict(list)
    slot_views: dict[str, list] = defaultdict(list)
    hook_views: dict[str, list] = defaultdict(list)
    ctr_samples: list = []
    eng_samples: list = []
    hook_style_views: dict[str, list] = defaultdict(list)
    quality_issues: list[dict] = []
    total_views = 0
    view_count = 0
    for entry in history:
        views = _entry_views(entry) or 0
        if views:
            total_views += views
            view_count += 1
        theme_views[(entry.get("topic") or "unknown").strip().lower()].append(views)
        poet_views[(entry.get("poet") or "unknown").strip().lower()].append(views)
        cap_views[(entry.get("caption_style") or entry.get("CAPTION_SCRIPT") or "unknown")].append(views)
        voice_views[(entry.get("voice") or entry.get("URDU_VOICE") or "unknown")].append(views)
        # Learn best publish slot (PKT hour) from actual performance.
        for fld in ("publish_at", "posted_at"):
            ts = entry.get(fld)
            if ts:
                try:
                    # publish_at is UTC ISO; convert to PKT hour
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    pkt = dt.astimezone(timezone.utc)  # Asia/Karachi = UTC+5
                    hour = (pkt.hour + 5) % 24
                    slot_views[str(hour)].append(views)
                    break
                except Exception:
                    pass
        issues = _detect_quality_issues(entry)
        if issues:
            quality_issues.append({"video_id": entry.get("youtube_video_id"),
                                   "title": entry.get("title"), "issues": issues})
        # Advanced signals: hook score, CTR, engagement (may be None pre-data)
        hook_views[entry.get("source", "unknown")].append(
            (views, _hook_score(entry)))
        hook_style_views[_hook_style(entry)].append(views)
        ctr = _estimate_ctr(entry)
        eng = _estimate_engagement(entry)
        if ctr is not None:
            ctr_samples.append(ctr)
        if eng is not None:
            eng_samples.append(eng)

    def _avg(vals: list) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _best_buckets(buckets: dict, min_n: int, order_desc: bool = True) -> list[dict]:
        out = []
        for k, vals in buckets.items():
            if len(vals) >= min_n and any(vals):
                out.append({"key": k, "n": len(vals), "avg_views": round(_avg(vals), 1)})
        return sorted(out, key=lambda x: x["avg_views"], reverse=order_desc)

    winning_themes = _best_buckets(theme_views, WINNER_MIN_SAMPLES)[:5]
    flop_themes = [t for t in _best_buckets(theme_views, WINNER_MIN_SAMPLES, order_desc=False)
                   if t["avg_views"] < FLOP_VIEWS][:5]
    winning_poets = _best_buckets(poet_views, WINNER_MIN_SAMPLES)[:5]
    flop_poets = [t for t in _best_buckets(poet_views, WINNER_MIN_SAMPLES, order_desc=False)
                  if t["avg_views"] < FLOP_VIEWS][:5]
    best_caption = _best_buckets(cap_views, MIN_SAMPLES)[:1]
    best_voice = _best_buckets(voice_views, MIN_SAMPLES)[:1]

    _with_views = [v for v in history if _entry_views(v) is not None]
    avg_views = _avg([_entry_views(v) for v in _with_views]) if _with_views else 0
    if avg_views >= WINNER_VIEWS:
        cadence = MAX_CADENCE
    elif avg_views >= 1000:
        cadence = max(1, MAX_CADENCE - 1)
    else:
        cadence = 1
    cadence = max(1, min(cadence, MAX_CADENCE))

    # Only videos that actually have analytics data count toward the throttle.
    # A Short uploaded <24-48h ago (or a channel whose analytics sync isn't
    # running) has no fetched views yet — that is NOT a flop. Counting it as 0
    # caused false throttling and a broken growth signal.
    mature = [v for v in history if _hours_since(v.get("posted_at")) is not None]
    recent = [v for v in mature[-THROTTLE_WINDOW:] if _entry_views(v) is not None]
    recent_avg = _avg([_entry_views(v) for v in recent]) if recent else 0
    throttle = bool(recent and len(recent) >= 3 and recent_avg < THROTTLE_VIEWS)

    traffic_insight = None
    if perf.get("traffic_sources"):
        traffic_insight = dict(sorted(perf["traffic_sources"].items(),
                                      key=lambda x: x[1], reverse=True)[:3])
    engagement_rate = perf.get("avg_engagement")

    avg_ctr = round(sum(ctr_samples) / len(ctr_samples), 2) if ctr_samples else None
    avg_engagement = round(sum(eng_samples) / len(eng_samples), 2) if eng_samples else None
    # average hook score across all videos (from hook_views buckets)
    _all_hooks = [h for bucket in hook_views.values() for _, h in bucket]
    avg_hook = round(sum(_all_hooks) / len(_all_hooks), 1) if _all_hooks else None

    # Best hook style by avg views (confidence-gated to >=2 samples)
    best_hook_frame = None
    _hook_cands = {k: v for k, v in hook_style_views.items() if len(v) >= 2 and any(v)}
    if _hook_cands:
        best_hook_frame = max(_hook_cands, key=lambda k: sum(_hook_cands[k]) / len(_hook_cands[k]))

    controls = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommended_cadence": cadence,
        "best_hook_frame": best_hook_frame,
        "avg_ctr": avg_ctr,
        "avg_engagement": avg_engagement,
        "avg_hook_score": avg_hook,
        "throttle": throttle,
        "throttle_reason": f"last {len(recent)} videos avg {recent_avg:.0f} views" if recent else "no data yet",
        "winning_themes": winning_themes,
        "flop_themes": flop_themes,
        "winning_poets": winning_poets,
        "flop_poets": flop_poets,
        "best_caption_style": best_caption[0]["key"] if best_caption else None,
        "best_voice": best_voice[0]["key"] if best_voice else None,
        "best_publish_slots": _learned_slots(slot_views),
        "traffic_source_insight": traffic_insight,
        "engagement_rate": engagement_rate,
        "avg_views_per_video": round(avg_views, 1),
        "quality_gate_min": MIN_QUALITY_SCORE,
        "quality_issues": quality_issues,
        "known_mistakes": [i["issues"][0] for i in quality_issues[:5]],
        "total_videos": len(history),
        "total_views": total_views,
        "videos_with_views": view_count,
    }
    _save_json(AUTONOMOUS_STATE_PATH, controls)
    logger.info("Autonomous: cadence=%d throttle=%s themes=%d poets=%d quality_issues=%d",
                cadence, throttle, len(winning_themes), len(winning_poets), len(quality_issues))
    return controls


def get_controls() -> dict:
    state = _load_json(AUTONOMOUS_STATE_PATH, {})
    if not state or not state.get("generated_at"):
        return analyse()
    return state


def should_block_theme(theme: str) -> bool:
    if not theme:
        return False
    t = theme.strip().lower()
    flops = {f["key"] for f in get_controls().get("flop_themes", [])}
    return t in flops


def should_block_poet(poet: str) -> bool:
    if not poet:
        return False
    p = poet.strip().lower()
    flops = {f["key"] for f in get_controls().get("flop_poets", [])}
    return p in flops


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(analyse(), indent=2, ensure_ascii=False))
