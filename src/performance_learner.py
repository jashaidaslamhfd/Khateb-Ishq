#!/usr/bin/env python3
"""AI Performance Learner — YouTube Analytics → viral pattern detection → smarter themes.

This module pulls channel analytics via the YouTube Data API, identifies which
videos over-perform (viral ratio = views / subscribers), and builds a feedback
loop so the theme selector, script generator, and scheduler all learn from
real audience data instead of blind randomization.

Architecture:
  1. Pull latest video stats from YouTube Analytics API
  2. Classify each video: viral / average / underperformer
  3. Extract patterns: winning themes, poets, time slots, voice, caption style
  4. Save performance profile to data/performance_profile.json
  5. Feed profile into theme_fetcher, script_generator, scheduler

Usage:
  from performance_learner import PerformanceLearner
  learner = PerformanceLearner()
  learner.refresh_stats()
  profile = learner.get_profile()
  best_themes = learner.recommend_themes()
  best_slots = learner.recommend_publish_slots()
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("performance_learner")

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = Path(os.environ.get("PERFORMANCE_PROFILE_PATH", str(ROOT / "data" / "performance_profile.json")))
HISTORY_PATH = Path(os.environ.get("VIDEO_HISTORY_PATH", str(ROOT / "data" / "video_history.json")))
STATS_CACHE_PATH = ROOT / "data" / "video_stats_cache.json"

# ── Viral thresholds ──────────────────────────────────────────────────────
# A video is "viral" if its views >= channel_subs * VIRAL_MULTIPLIER.
# For a small channel (1K subs) with a 50K view video, that's 50x = viral.
VIRAL_MULTIPLIER = float(os.environ.get("VIRAL_MULTIPLIER", "10"))
AVERAGE_MULTIPLIER = float(os.environ.get("AVERAGE_MULTIPLIER", "3"))
MIN_VIEWS_FOR_SIGNAL = int(os.environ.get("MIN_VIEWS_FOR_SIGNAL", "100"))


class PerformanceLearner:
    """Learns from YouTube Analytics which content patterns drive views."""

    def __init__(self):
        self.profile = self._load_profile()
        self.stats_cache = self._load_stats_cache()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load_profile(self) -> dict:
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "version": 2,
                "last_updated": None,
                "channel_stats": {"subscribers": 0, "total_views": 0, "total_videos": 0},
                "top_themes": [],          # [{theme, avg_views, viral_ratio, count}]
                "top_poets": [],           # [{poet, avg_views, viral_ratio, count}]
                "top_publish_slots": [],   # [{slot, avg_views, count}]
                "top_voices": [],          # [{voice, avg_views, count}]
                "top_caption_styles": [],  # [{style, avg_views, count}]
                "viral_patterns": [],      # [{pattern, examples, confidence}]
                "seasonal_peaks": [],      # [{month, theme_hint, avg_views}]
                "recommendations": {},     # {theme_hints, slot_hints, poet_hints}
            }

    def _save_profile(self) -> None:
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROFILE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.profile, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PROFILE_PATH)
        logger.info("Performance profile saved → %s", PROFILE_PATH)

    def _load_stats_cache(self) -> dict:
        try:
            return json.loads(STATS_CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"videos": {}, "last_pull": None}

    def _save_stats_cache(self) -> None:
        STATS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATS_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.stats_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATS_CACHE_PATH)

    # ── YouTube Analytics Pull ─────────────────────────────────────────────

    def _yt_client(self):
        """Build YouTube Data API client (same OAuth as uploader)."""
        import google.oauth2.credentials
        from googleapiclient.discovery import build

        creds = google.oauth2.credentials.Credentials(
            token=None,
            refresh_token=os.environ.get("REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube.readonly",
                    "https://www.googleapis.com/auth/yt-analytics.readonly"],
        )
        return build("youtube", "v3", credentials=creds)

    def pull_video_stats(self, max_pages: int = 5) -> int:
        """Pull latest view counts for all channel videos from YouTube Data API.
        Returns number of videos updated."""
        try:
            yt = self._yt_client()
        except Exception as exc:
            logger.warning("YouTube API client failed: %s — using history-only mode", exc)
            return 0

        updated = 0
        page_token = None
        for _ in range(max_pages):
            try:
                resp = yt.search().list(
                    part="id,snippet",
                    forMine=True,
                    type="video",
                    maxResults=50,
                    pageToken=page_token,
                ).execute()
            except Exception as exc:
                logger.warning("YouTube search.list failed: %s", exc)
                break

            video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]
            if not video_ids:
                break

            # Batch fetch stats
            try:
                stats_resp = yt.videos().list(
                    part="statistics,snippet",
                    id=",".join(video_ids),
                ).execute()
            except Exception as exc:
                logger.warning("YouTube videos.list failed: %s", exc)
                break

            for item in stats_resp.get("items", []):
                vid = item["id"]
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                self.stats_cache["videos"][vid] = {
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "published_at": snippet.get("publishedAt", ""),
                    "tags": snippet.get("tags", []),
                    "description": snippet.get("description", "")[:500],
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                updated += 1

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        self.stats_cache["last_pull"] = datetime.now(timezone.utc).isoformat()
        self._save_stats_cache()
        logger.info("Pulled stats for %d videos", updated)
        return updated

    # ── Pattern Analysis ───────────────────────────────────────────────────

    def _classify_video(self, views: int, subs: int) -> str:
        """Classify a video as viral / average / underperformer."""
        if subs <= 0:
            return "average" if views >= MIN_VIEWS_FOR_SIGNAL else "underperformer"
        ratio = views / subs
        if ratio >= VIRAL_MULTIPLIER:
            return "viral"
        if ratio >= AVERAGE_MULTIPLIER:
            return "average"
        return "underperformer"

    def _merge_with_history(self) -> List[dict]:
        """Merge YouTube stats with video_history.json for richer analysis."""
        history = []
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

        stats_videos = self.stats_cache.get("videos", {})
        # Build a lookup: video_id → stats
        stats_by_id = {vid: data for vid, data in stats_videos.items()}

        merged = []
        for record in history:
            vid = record.get("youtube_video_id")
            if vid and vid in stats_by_id:
                record["views"] = stats_by_id[vid].get("views", 0)
                record["likes"] = stats_by_id[vid].get("likes", 0)
                record["comments_count"] = stats_by_id[vid].get("comments", 0)
            merged.append(record)

        # Also include videos from stats that aren't in history
        history_ids = {r.get("youtube_video_id") for r in history if r.get("youtube_video_id")}
        for vid, data in stats_by_id.items():
            if vid not in history_ids:
                merged.append({
                    "youtube_video_id": vid,
                    "title": data.get("title", ""),
                    "views": data.get("views", 0),
                    "likes": data.get("likes", 0),
                    "comments_count": data.get("comments", 0),
                    "posted_at": data.get("published_at", ""),
                    "topic": "",
                    "poet": "",
                    "source": "",
                })

        return merged

    def analyze_patterns(self) -> None:
        """Run full pattern analysis on merged data and update profile."""
        merged = self._merge_with_history()
        if not merged:
            logger.warning("No data to analyze — run pull_video_stats() first or wait for history")
            return

        subs = self.profile.get("channel_stats", {}).get("subscribers", 0)
        if subs == 0:
            # Estimate subs from median views
            all_views = [r.get("views", 0) for r in merged if r.get("views", 0) > 0]
            if all_views:
                subs = max(1, sorted(all_views)[len(all_views) // 2] // 3)
            self.profile["channel_stats"]["subscribers"] = subs

        self.profile["channel_stats"]["total_videos"] = len(merged)
        self.profile["channel_stats"]["total_views"] = sum(r.get("views", 0) for r in merged)

        # ── Theme analysis ─────────────────────────────────────────────────
        theme_stats: Dict[str, dict] = {}
        for r in merged:
            topic = (r.get("topic") or "").strip()
            if not topic:
                continue
            views = r.get("views", 0)
            if topic not in theme_stats:
                theme_stats[topic] = {"views": [], "viral_count": 0, "count": 0}
            theme_stats[topic]["views"].append(views)
            theme_stats[topic]["count"] += 1
            if self._classify_video(views, subs) == "viral":
                theme_stats[topic]["viral_count"] += 1

        top_themes = []
        for topic, data in theme_stats.items():
            avg = sum(data["views"]) / max(1, len(data["views"]))
            viral_ratio = data["viral_count"] / max(1, data["count"])
            if avg >= MIN_VIEWS_FOR_SIGNAL:
                top_themes.append({
                    "theme": topic,
                    "avg_views": int(avg),
                    "viral_ratio": round(viral_ratio, 3),
                    "count": data["count"],
                })
        top_themes.sort(key=lambda x: -x["avg_views"])
        self.profile["top_themes"] = top_themes[:30]

        # ── Poet analysis ──────────────────────────────────────────────────
        poet_stats: Dict[str, dict] = {}
        for r in merged:
            poet = (r.get("poet") or "").strip()
            if not poet:
                continue
            views = r.get("views", 0)
            if poet not in poet_stats:
                poet_stats[poet] = {"views": [], "viral_count": 0, "count": 0}
            poet_stats[poet]["views"].append(views)
            poet_stats[poet]["count"] += 1
            if self._classify_video(views, subs) == "viral":
                poet_stats[poet]["viral_count"] += 1

        top_poets = []
        for poet, data in poet_stats.items():
            avg = sum(data["views"]) / max(1, len(data["views"]))
            viral_ratio = data["viral_count"] / max(1, data["count"])
            if avg >= MIN_VIEWS_FOR_SIGNAL:
                top_poets.append({
                    "poet": poet,
                    "avg_views": int(avg),
                    "viral_ratio": round(viral_ratio, 3),
                    "count": data["count"],
                })
        top_poets.sort(key=lambda x: -x["avg_views"])
        self.profile["top_poets"] = top_poets[:15]

        # ── Publish slot analysis ──────────────────────────────────────────
        slot_stats: Dict[str, dict] = {}
        for r in merged:
            posted = r.get("posted_at") or r.get("publish_at") or ""
            if not posted:
                continue
            try:
                dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                # Convert to PKT
                from datetime import timezone as tz
                pkt = dt.astimezone(tz(timedelta(hours=5)))
                slot = f"{pkt.hour:02d}:00"
            except Exception:
                continue
            views = r.get("views", 0)
            if slot not in slot_stats:
                slot_stats[slot] = {"views": [], "count": 0}
            slot_stats[slot]["views"].append(views)
            slot_stats[slot]["count"] += 1

        top_slots = []
        for slot, data in slot_stats.items():
            avg = sum(data["views"]) / max(1, len(data["views"]))
            if avg >= MIN_VIEWS_FOR_SIGNAL:
                top_slots.append({"slot": slot, "avg_views": int(avg), "count": data["count"]})
        top_slots.sort(key=lambda x: -x["avg_views"])
        self.profile["top_publish_slots"] = top_slots[:10]

        # ── Viral pattern detection ────────────────────────────────────────
        viral_videos = [r for r in merged if self._classify_video(r.get("views", 0), subs) == "viral"]
        patterns = []
        if viral_videos:
            # Theme clusters among viral videos
            viral_themes = {}
            for r in viral_videos:
                topic = (r.get("topic") or "").strip().lower()
                if not topic:
                    continue
                viral_themes[topic] = viral_themes.get(topic, 0) + 1

            # Top viral theme clusters
            for theme, count in sorted(viral_themes.items(), key=lambda x: -x[1])[:5]:
                patterns.append({
                    "pattern": "viral_theme_cluster",
                    "theme": theme,
                    "count": count,
                    "confidence": min(1.0, count / max(1, len(viral_videos))),
                })

            # Poet clusters among viral
            viral_poets = {}
            for r in viral_videos:
                poet = (r.get("poet") or "").strip().lower()
                if not poet:
                    continue
                viral_poets[poet] = viral_poets.get(poet, 0) + 1
            for poet, count in sorted(viral_poets.items(), key=lambda x: -x[1])[:3]:
                patterns.append({
                    "pattern": "viral_poet_cluster",
                    "poet": poet,
                    "count": count,
                    "confidence": min(1.0, count / max(1, len(viral_videos))),
                })

            # Time-of-day clusters among viral
            viral_hours = {}
            for r in viral_videos:
                posted = r.get("posted_at") or r.get("publish_at") or ""
                if not posted:
                    continue
                try:
                    dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                    from datetime import timezone as tz
                    pkt = dt.astimezone(tz(timedelta(hours=5)))
                    hour = pkt.hour
                except Exception:
                    continue
                viral_hours[hour] = viral_hours.get(hour, 0) + 1
            for hour, count in sorted(viral_hours.items(), key=lambda x: -x[1])[:3]:
                patterns.append({
                    "pattern": "viral_time_slot",
                    "hour": hour,
                    "count": count,
                    "confidence": min(1.0, count / max(1, len(viral_videos))),
                })

        self.profile["viral_patterns"] = patterns

        # ── Seasonal peaks ─────────────────────────────────────────────────
        month_stats: Dict[int, dict] = {}
        for r in merged:
            posted = r.get("posted_at") or r.get("publish_at") or ""
            if not posted:
                continue
            try:
                dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                month = dt.month
            except Exception:
                continue
            views = r.get("views", 0)
            if month not in month_stats:
                month_stats[month] = {"views": [], "count": 0}
            month_stats[month]["views"].append(views)
            month_stats[month]["count"] += 1

        seasonal = []
        for month, data in month_stats.items():
            avg = sum(data["views"]) / max(1, len(data["views"]))
            seasonal.append({
                "month": month,
                "avg_views": int(avg),
                "count": data["count"],
            })
        seasonal.sort(key=lambda x: x["month"])
        self.profile["seasonal_peaks"] = seasonal

        # ── Build recommendations ──────────────────────────────────────────
        self._build_recommendations()

        self.profile["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_profile()
        logger.info("Pattern analysis complete — %d themes, %d poets, %d viral patterns",
                    len(self.profile["top_themes"]), len(self.profile["top_poets"]),
                    len(self.profile["viral_patterns"]))

    def _build_recommendations(self) -> None:
        """Generate actionable recommendations from analyzed data."""
        recs = {"theme_hints": [], "slot_hints": [], "poet_hints": [], "voice_hints": []}

        # Top 10 themes by avg_views
        for t in self.profile.get("top_themes", [])[:10]:
            recs["theme_hints"].append({"theme": t["theme"], "weight": t["avg_views"]})

        # Best publish slots
        for s in self.profile.get("top_publish_slots", [])[:5]:
            recs["slot_hints"].append({"slot": s["slot"], "weight": s["avg_views"]})

        # Best poets
        for p in self.profile.get("top_poets", [])[:5]:
            recs["poet_hints"].append({"poet": p["poet"], "weight": p["avg_views"]})

        # Viral pattern signals
        for vp in self.profile.get("viral_patterns", []):
            if vp["confidence"] >= 0.3:
                if vp["pattern"] == "viral_theme_cluster":
                    recs["theme_hints"].append({"theme": vp["theme"], "weight": vp["confidence"] * 10000})
                elif vp["pattern"] == "viral_poet_cluster":
                    recs["poet_hints"].append({"poet": vp["poet"], "weight": vp["confidence"] * 10000})

        self.profile["recommendations"] = recs

    # ── Public API ─────────────────────────────────────────────────────────

    def refresh_stats(self) -> dict:
        """Pull latest stats and analyze patterns. Returns profile summary."""
        self.pull_video_stats()
        self.analyze_patterns()
        return self.get_summary()

    def get_profile(self) -> dict:
        """Return the current performance profile."""
        return self.profile

    def get_summary(self) -> dict:
        """Return a human-readable summary of the profile."""
        p = self.profile
        return {
            "channel_subs": p["channel_stats"].get("subscribers", 0),
            "total_views": p["channel_stats"].get("total_views", 0),
            "total_videos": p["channel_stats"].get("total_videos", 0),
            "top_5_themes": [t["theme"] for t in p.get("top_themes", [])[:5]],
            "top_5_poets": [p_["poet"] for p_ in p.get("top_poets", [])[:5]],
            "viral_patterns_count": len(p.get("viral_patterns", [])),
            "last_updated": p.get("last_updated"),
        }

    def recommend_themes(self, count: int = 5) -> List[dict]:
        """Return top N theme recommendations weighted by performance data."""
        recs = self.profile.get("recommendations", {}).get("theme_hints", [])
        if not recs:
            return []
        recs.sort(key=lambda x: -x["weight"])
        return recs[:count]

    def recommend_publish_slots(self, count: int = 3) -> List[dict]:
        """Return top N publish slot recommendations."""
        recs = self.profile.get("recommendations", {}).get("slot_hints", [])
        if not recs:
            return []
        recs.sort(key=lambda x: -x["weight"])
        return recs[:count]

    def recommend_poets(self, count: int = 3) -> List[dict]:
        """Return top N poet recommendations."""
        recs = self.profile.get("recommendations", {}).get("poet_hints", [])
        if not recs:
            return []
        recs.sort(key=lambda x: -x["weight"])
        return recs[:count]

    def should_boost_theme(self, theme: str) -> float:
        """Return a boost factor (0.0-2.0) for a given theme based on performance.
        Themes with strong historical performance get higher boost."""
        theme_lower = theme.strip().lower()
        for rec in self.profile.get("recommendations", {}).get("theme_hints", []):
            if rec["theme"].lower() == theme_lower:
                # Normalize: weight is avg_views, scale to 0.5-2.0
                return min(2.0, max(0.5, 1.0 + (rec["weight"] / 10000)))
        return 1.0

    def should_boost_poet(self, poet: str) -> float:
        """Return a boost factor for a given poet."""
        poet_lower = poet.strip().lower()
        for rec in self.profile.get("recommendations", {}).get("poet_hints", []):
            if rec["poet"].lower() == poet_lower:
                return min(2.0, max(0.5, 1.0 + (rec["weight"] / 10000)))
        return 1.0


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    learner = PerformanceLearner()
    summary = learner.refresh_stats()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n🏆 Top Theme Recommendations:")
    for t in learner.recommend_themes(5):
        print(f"  • {t['theme']} (weight: {t['weight']})")
    print("\n📅 Best Publish Slots:")
    for s in learner.recommend_publish_slots(3):
        print(f"  • {s['slot']} (weight: {s['weight']})")
    print("\n✍️ Best Poets:")
    for p in learner.recommend_poets(3):
        print(f"  • {p['poet']} (weight: {p['weight']})")
