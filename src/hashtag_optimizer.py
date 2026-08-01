#!/usr/bin/env python3
"""Hashtag Optimizer — YouTube search trends + competitor analysis → optimal hashtags.

This module generates data-driven hashtags for each video by:
  1. Analyzing YouTube search autocomplete for Urdu poetry keywords
  2. Checking competitor hashtag usage on viral Urdu poetry videos
  3. Learning from the channel's own performance data which tags drive views
  4. Applying YouTube's hashtag best practices (max 15 tags, 500 chars)

Usage:
  from hashtag_optimizer import HashtagOptimizer
  opt = HashtagOptimizer()
  tags = opt.optimize(script_data={"title": "...", "poet": "...", "topic": "..."})
"""

import hashlib
import json
import logging
import os
import re
import random
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("hashtag_optimizer")

ROOT = Path(__file__).resolve().parents[1]
HASHTAG_CACHE_PATH = ROOT / "data" / "hashtag_cache.json"
MAX_TAGS = int(os.environ.get("MAX_HASHTAGS", "15"))
MAX_TAG_CHARS = int(os.environ.get("MAX_HASHTAG_CHARS", "500"))

# ── Seed keywords for YouTube search trend scraping ────────────────────────
URDU_POETRY_SEEDS = [
    # ── Channel's TOP search terms (real analytics 2026-08-01) ──
    "poetry background music", "sad shayari background music",
    "background music for poetry", "poetry bg music",
    "sad background music", "copyright free background music",
    "no copyright music", "background music poetry",
    # ── General poetry seeds ──
    "urdu poetry sad", "sad shayari status", "ghalib poetry",
    "2 line poetry", "heart touching shayari",
    "ishq shayari", "dukh shayari", "dard bhari shayari",
    "tanhai poetry", "mohabbat poetry urdu", "barish shayari",
]

# ── Pre-validated high-performing hashtag clusters ─────────────────────────
STATIC_CLUSTERS = {
    # ── REAL channel search data (owner provided 2026-08-01) ──
    "channel_top_search": [
        "poetrybackgroundmusic", "sadshayaribackgroundmusic",
        "backgroundmusicforpoetry", "backgroundmusicpoetry",
        "poetrybgmusic", "sadbackgroundmusic",
        "copyrightfreebackgroundmusic", "nocopyrightmusic",
    ],
    "poetry_core": ["urdupoetry", "shayari", "sadpoetry", "urdushayari", "poetry"],
    "sad_status": ["sadstatus", "dukhistatus", "sadshayari", "dard", "gham"],
    "heart_touching": ["hearttouching", "hearttouchingshayari", "emotionalpoetry"],
    "viral_hooks": ["viral", "trending", "foryou", "fyp", "viralpoetry"],
    "poet_specific": ["ghalib", "iqbal", "mir", "allamaiqbal", "mirzaghalib"],
    "format": ["2linepoetry", "2lineshayari", "shortpoetry", "shayaristatus"],
    "romantic": ["ishq", "mohabbat", "lovepoetry", "romanticpoetry", "ishqshayari"],
    "sufi": ["sufipoetry", "sufi", "bullehshah", "spiritualpoetry"],
    "rain_mood": ["barish", "rainypoetry", "barsaat", "rainshayari"],
    "night_mood": ["raat", "nightpoetry", "tanhai", "raatshayari"],
}


class HashtagOptimizer:
    """Generates optimized hashtags based on trends and performance data."""

    def __init__(self):
        self.cache = self._load_cache()
        self._performance = self._load_performance()

    def _load_cache(self) -> dict:
        try:
            return json.loads(HASHTAG_CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"trends": {}, "competitor_tags": {}, "last_updated": None}

    def _save_cache(self) -> None:
        HASHTAG_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = HASHTAG_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(HASHTAG_CACHE_PATH)

    def _load_performance(self) -> dict:
        perf_path = ROOT / "data" / "performance_profile.json"
        try:
            return json.loads(perf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ── YouTube Autosuggest Scraping ──────────────────────────────────────

    def _fetch_autosuggest(self, seed: str) -> List[str]:
        """Fetch YouTube search suggestions for a seed keyword."""
        try:
            encoded = urllib.parse.quote(seed)
            url = f"http://suggestqueries.google.com/complete/search?client=youtube&hl=ur&ds=yt&q={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8", "ignore")
                suggestions = re.findall(r'"([^"]+)"', content)
                return [s for s in suggestions if s.lower() != seed.lower() and len(s) > len(seed)][:10]
        except Exception as exc:
            logger.warning("Autosuggest failed for '%s': %s", seed, exc)
            return []

    def refresh_trends(self) -> int:
        """Refresh YouTube search trend data. Returns number of new suggestions."""
        total = 0
        for seed in URDU_POETRY_SEEDS:
            suggestions = self._fetch_autosuggest(seed)
            self.cache["trends"][seed] = {
                "suggestions": suggestions,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            total += len(suggestions)
        self.cache["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_cache()
        logger.info("Refreshed trends — %d new suggestions from %d seeds", total, len(URDU_POETRY_SEEDS))
        return total

    # ── Tag Extraction from Trends ─────────────────────────────────────────

    def _extract_trending_tags(self) -> List[str]:
        """Extract high-potential hashtags from cached trend data."""
        tags = []
        seen = set()
        for seed, data in self.cache.get("trends", {}).items():
            for suggestion in data.get("suggestions", []):
                # Convert search suggestion to hashtag format
                # "sad urdu poetry status" → "sadurdupoetrystatus"
                tag = re.sub(r'[^a-zA-Z0-9]', '', suggestion.lower())
                if tag and len(tag) >= 4 and tag not in seen and len(tag) <= 30:
                    tags.append(tag)
                    seen.add(tag)
        return tags

    # ── Performance-weighted Tags ──────────────────────────────────────────

    def _performance_weighted_tags(self) -> Dict[str, float]:
        """Get tags weighted by historical performance data."""
        weighted = {}
        # From video stats cache
        stats_path = ROOT / "data" / "video_stats_cache.json"
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            for vid, data in stats.get("videos", {}).items():
                views = data.get("views", 0)
                tags = data.get("tags", [])
                for tag in tags:
                    tag_clean = re.sub(r'[^a-zA-Z0-9]', '', tag.lower())
                    if tag_clean:
                        weighted[tag_clean] = weighted.get(tag_clean, 0) + views
        except (OSError, json.JSONDecodeError):
            pass

        return weighted

    # ── Main Optimization ──────────────────────────────────────────────────

    def optimize(self, script_data: dict, extra_tags: List[str] = None) -> List[str]:
        """Generate optimized hashtags for a video.

        Strategy:
          1. Core tags from the video's topic/poet/source
          2. Trending tags from YouTube autosuggest
          3. Performance-weighted tags from channel history
          4. Static cluster tags for guaranteed coverage
          5. Deduplicate, trim to YouTube limits, return ordered by priority
        """
        final_tags = []
        used = set()

        def add_tag(tag: str, priority: int = 0) -> None:
            """Add a tag if not already used. Priority: 0=highest, 3=lowest."""
            tag_clean = re.sub(r'[^a-zA-Z0-9]', '', tag.lower().replace("#", ""))
            if not tag_clean or len(tag_clean) < 3 or tag_clean in used:
                return
            used.add(tag_clean)
            final_tags.append((tag_clean, priority))

        # Priority 0: Video-specific tags (highest priority)
        title = (script_data.get("title") or "").strip()
        poet = (script_data.get("poet") or "").strip()
        topic = (script_data.get("topic") or "").strip()
        source = (script_data.get("source") or "").strip()

        if topic:
            add_tag(topic, 0)
        if poet and poet.lower() != "original":
            add_tag(poet, 0)
        add_tag("khatebeishq", 0)  # Channel branding

        # Priority 1: Channel's TOP search terms (real analytics data)
        for tag in STATIC_CLUSTERS["channel_top_search"][:4]:
            add_tag(tag, 1)
        # Priority 1: Core poetry tags
        for tag in STATIC_CLUSTERS["poetry_core"][:2]:
            add_tag(tag, 1)
        for tag in STATIC_CLUSTERS["sad_status"][:2]:
            add_tag(tag, 1)

        # Priority 1: Format tags
        for tag in STATIC_CLUSTERS["format"][:2]:
            add_tag(tag, 1)

        # Priority 2: Trending tags
        trending = self._extract_trending_tags()
        for tag in trending[:5]:
            add_tag(tag, 2)

        # Priority 2: Performance-weighted tags
        perf_tags = self._performance_weighted_tags()
        if perf_tags:
            top_perf = sorted(perf_tags.items(), key=lambda x: -x[1])[:5]
            for tag, weight in top_perf:
                add_tag(tag, 2)

        # Priority 2: Mood-specific tags
        topic_lower = (topic + " " + title).lower()
        if any(kw in topic_lower for kw in ["ishq", "mohabbat", "love", "pyar"]):
            for tag in STATIC_CLUSTERS["romantic"][:2]:
                add_tag(tag, 2)
        if any(kw in topic_lower for kw in ["sufi", "bulleh", "spiritual"]):
            for tag in STATIC_CLUSTERS["sufi"][:2]:
                add_tag(tag, 2)
        if any(kw in topic_lower for kw in ["barish", "rain", "barsaat"]):
            for tag in STATIC_CLUSTERS["rain_mood"][:2]:
                add_tag(tag, 2)
        if any(kw in topic_lower for kw in ["raat", "night", "tanhai"]):
            for tag in STATIC_CLUSTERS["night_mood"][:2]:
                add_tag(tag, 2)

        # Priority 3: Viral hooks
        for tag in STATIC_CLUSTERS["viral_hooks"][:2]:
            add_tag(tag, 3)

        # Priority 3: Extra tags passed in
        if extra_tags:
            for tag in extra_tags:
                add_tag(tag, 3)

        # Sort by priority, then trim to YouTube limits
        final_tags.sort(key=lambda x: x[1])
        result = []
        total_chars = 0
        for tag, _ in final_tags:
            tag_with_hash = f"#{tag}"
            if len(result) >= MAX_TAGS:
                break
            if total_chars + len(tag_with_hash) + 1 > MAX_TAG_CHARS:
                break
            result.append(tag)
            total_chars += len(tag_with_hash) + 1

        logger.info("Optimized %d hashtags for '%s'", len(result), title[:40] if title else "video")
        return result

    def optimize_title_hashtags(self, title: str, top_tags: List[str] = None) -> str:
        """Append 3 high-impact hashtags to the video title (YouTube best practice).
        Titles with 1-3 hashtags get more discoverability in search."""
        top_tags = top_tags or self.optimize(script_data={"title": title, "topic": title})
        # Pick top 3 for title
        title_tags = [f"#{t}" for t in top_tags[:3]]
        suffix = " ".join(title_tags)
        combined = f"{title} {suffix}"
        # YouTube title limit: 100 chars
        if len(combined) > 100:
            combined = f"{title[:100 - len(suffix) - 1]} {suffix}"
        return combined[:100]


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    opt = HashtagOptimizer()
    print("Refreshing YouTube search trends...")
    opt.refresh_trends()
    tags = opt.optimize(script_data={
        "title": "غمِ دل",
        "poet": "Ghalib",
        "topic": "juda'i gham",
        "source": "classic",
    })
    print(f"\nOptimized {len(tags)} hashtags:")
    for t in tags:
        print(f"  #{t}")
