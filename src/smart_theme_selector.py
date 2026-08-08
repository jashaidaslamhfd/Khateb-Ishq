#!/usr/bin/env python3
"""Smart Theme Selector — Performance-learned + trend-predicted theme selection.

This module replaces the basic theme_fetcher with an intelligent theme
selection system that learns from:
  1. Channel's own performance data (which themes went viral)
  2. Trend predictions (what's trending now)
  3. Seasonal patterns (what works in this month)
  4. Competitor hijacker (what's working for competitors)
  5. Catalog deduplication (never repeat a theme)

Usage:
  from smart_theme_selector import SmartThemeSelector
  selector = SmartThemeSelector()
  theme = selector.select()
  print(f"Selected: {theme['topic']} (strategy: {theme['strategy']})")
"""

import json
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smart_theme_selector")

ROOT = Path(__file__).resolve().parents[1]
THEMES_PATH = Path(os.environ.get("POETRY_THEMES_PATH", str(ROOT / "data" / "poetry_themes.json")))
HISTORY_PATH = Path(os.environ.get("VIDEO_HISTORY_PATH", str(ROOT / "data" / "video_history.json")))


class SmartThemeSelector:
    """Intelligent theme selection that learns from performance data."""

    def __init__(self):
        self.performance = self._load_performance()
        self.catalog = self._load_catalog()
        self.used_themes = self._load_used_themes()

    def _load_performance(self) -> dict:
        perf_path = ROOT / "data" / "performance_profile.json"
        try:
            return json.loads(perf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_catalog(self) -> list:
        try:
            return json.loads(THEMES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _load_used_themes(self) -> set:
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            return {str(v.get("topic", "")).strip().lower() for v in history if v.get("topic")}
        except (OSError, json.JSONDecodeError):
            return set()

    def _refresh_used_themes(self) -> None:
        """Refresh used themes set (in case history was updated)."""
        self.used_themes = self._load_used_themes()

    # ── Strategy Selection ─────────────────────────────────────────────────

    def _select_strategy(self) -> str:
        """Decide which theme selection strategy to use based on data availability.

        Strategy weights:
          - trend_predictor: 35% (if data available)
          - performance_learned: 30% (if data available)
          - competitor_hijack: 15% (if data available)
          - seasonal: 10% (always available)
          - catalog_random: 10% (fallback)
        """
        has_performance = bool(self.performance.get("top_themes"))
        has_trends = (ROOT / "data" / "trend_predictions.json").exists()

        strategies = []
        if has_trends:
            strategies.extend([("trend_predictor", 35)])
        if has_performance:
            strategies.extend([("performance_learned", 30)])
        strategies.extend([
            ("competitor_hijack", 15),
            ("seasonal", 10),
            ("catalog_random", 10),
        ])

        # Weighted random selection
        total = sum(w for _, w in strategies)
        r = random.random() * total
        cumulative = 0
        for strategy, weight in strategies:
            cumulative += weight
            if r <= cumulative:
                return strategy
        return "catalog_random"

    # ── Strategy Implementations ───────────────────────────────────────────

    def _strategy_trend_predictor(self) -> Optional[dict]:
        """Select theme from trend predictions."""
        try:
            from trend_predictor import TrendPredictor
            predictor = TrendPredictor()
            best = predictor.get_best_topic(exclude=list(self.used_themes))
            if best:
                return {
                    "topic": best["topic"],
                    "series_title": f"Kalam #1: {best['topic'][:30]}",
                    "strategy": "trend_predictor",
                    "source": best.get("source", "trend"),
                    "confidence": best.get("confidence", 0),
                    "score": best.get("score", 0),
                }
        except Exception as exc:
            logger.warning("Trend predictor strategy failed: %s", exc)
        return None

    def _strategy_performance_learned(self) -> Optional[dict]:
        """Select theme from performance-learned data."""
        try:
            from performance_learner import PerformanceLearner
            learner = PerformanceLearner()
            recs = learner.recommend_themes(count=10)
            for rec in recs:
                if rec["theme"].lower().strip() not in self.used_themes:
                    return {
                        "topic": rec["theme"],
                        "series_title": f"Kalam #1: {rec['theme'][:30]}",
                        "strategy": "performance_learned",
                        "source": "performance_profile",
                        "weight": rec["weight"],
                    }
        except Exception as exc:
            logger.warning("Performance-learned strategy failed: %s", exc)
        return None

    def _strategy_competitor_hijack(self) -> Optional[dict]:
        """Select theme from competitor hijacker."""
        try:
            from competitor_hijacker_urdu import get_hijacked_viral_topic_ur
            chosen = get_hijacked_viral_topic_ur(list(self.used_themes))
            return {
                "topic": chosen["topic"],
                "series_title": f"Kalam #1: {chosen['topic'][:30]}",
                "strategy": "competitor_hijack",
                "source": chosen.get("source", "viral_hijack"),
                "score": chosen.get("score", 0),
            }
        except Exception as exc:
            logger.warning("Competitor hijack strategy failed: %s", exc)
        return None

    def _strategy_seasonal(self) -> Optional[dict]:
        """Select theme based on current season/month."""
        # Pakistan timezone
        pkt = datetime.now(timezone.utc) + timedelta(hours=5)
        month = pkt.month

        seasonal_themes = {
            1: ["sardi raat tanhai", "naye saal ki umeed", "andheri sardi raat"],
            2: ["mohabbat juda'i", "ishq aur dard", "dil ki baat"],
            3: ["bahar aayi", "basant shayari", "roza dua shayari"],
            4: ["roza dua shayari", "ramzan mubarak poetry", "eid mubarak shayari"],
            5: ["eid mubarak shayari", "chaand raat poetry"],
            6: ["garmi yaad shayari", "tanhai"],
            7: ["barish shayari", "baarish mein tanhai", "mausam barish poetry"],
            8: ["barish aur yaad", "pakistan zindabad poetry", "14 august shayari"],
            9: ["yaadon ka mausam", "defence day poetry"],
            10: ["khirki patton ki shayari", "mukhtasar si zindagi"],
            11: ["sardi aur dard", "shaadi shayari", "iqbal day poetry"],
            12: ["sardi raat gham", "saal guzar gaya", "quaid day poetry"],
        }

        themes = seasonal_themes.get(month, [])
        if not themes:
            return None

        # Filter out used themes
        fresh = [t for t in themes if t.lower().strip() not in self.used_themes]
        if not fresh:
            fresh = themes

        topic = random.choice(fresh)
        return {
            "topic": topic,
            "series_title": f"Kalam #1: {topic[:30]}",
            "strategy": "seasonal",
            "source": "seasonal_calendar",
            "month": month,
        }

    def _strategy_catalog_random(self) -> Optional[dict]:
        """Fallback: select from catalog with deduplication."""
        if not self.catalog:
            return {"topic": "gham juda'i", "series_title": "Kalam #1: Gham",
                    "strategy": "catalog_random", "source": "fallback"}

        fresh = [t for t in self.catalog if t["theme"].strip().lower() not in self.used_themes]
        if not fresh:
            fresh = self.catalog  # catalog exhausted → restart

        chosen = random.choice(fresh[-400:] if len(fresh) > 400 else fresh)
        return {
            "topic": chosen["theme"],
            "series_title": chosen.get("series_title", f"Kalam #1: {chosen['theme'][:30]}"),
            "strategy": "catalog_random",
            "source": "poetry_series",
        }

    # ── Main Selection ─────────────────────────────────────────────────────

    def select(self, strategy: str = None) -> dict:
        """Select the best theme using the optimal strategy.

        If strategy is specified, uses that strategy directly.
        Otherwise, auto-selects the best strategy based on available data.
        """
        self._refresh_used_themes()

        # Check if TOPIC_STRATEGY env forces a specific strategy
        forced = strategy or os.environ.get("TOPIC_STRATEGY", "smart").strip().lower()

        if forced == "smart":
            chosen_strategy = self._select_strategy()
        else:
            # Map old strategy names
            strategy_map = {
                "competitor_hijack": "competitor_hijack",
                "viral_hijack": "competitor_hijack",
                "poetry_series": "catalog_random",
                "performance": "performance_learned",
                "trend": "trend_predictor",
                "seasonal": "seasonal",
            }
            chosen_strategy = strategy_map.get(forced, "catalog_random")

        # Try the selected strategy
        strategies = {
            "trend_predictor": self._strategy_trend_predictor,
            "performance_learned": self._strategy_performance_learned,
            "competitor_hijack": self._strategy_competitor_hijack,
            "seasonal": self._strategy_seasonal,
            "catalog_random": self._strategy_catalog_random,
        }

        handler = strategies.get(chosen_strategy)
        if handler:
            result = handler()
            if result:
                logger.info("🎯 Theme selected via %s: '%s'", chosen_strategy, result["topic"])
                return self._autonomous_reroute(result)

        # Fallback chain: try each strategy in order of priority
        for strategy_name in ["trend_predictor", "performance_learned",
                              "competitor_hijack", "seasonal", "catalog_random"]:
            handler = strategies.get(strategy_name)
            if handler:
                result = handler()
                if result:
                    logger.info("🎯 Theme selected via fallback %s: '%s'", strategy_name, result["topic"])
                    return self._autonomous_reroute(result)

        # Ultimate fallback
        return {
            "topic": "gham juda'i — raat ke do bajay",
            "series_title": "Kalam #1: Gham",
            "strategy": "ultimate_fallback",
            "source": "hardcoded",
        }

    def _autonomous_reroute(self, result: dict) -> dict:
        """Route the chosen theme through the autonomous ML brain.

        Blocks proven-flop themes/poets (implementation, not advice) and
        attaches learned caption/voice/slot preferences. Never hard-fails.
        """
        try:
            from autonomous_controller import get_controls, should_block_poet, should_block_theme
            controls = get_controls()
            topic = (result.get("topic") or "").strip()
            poet = (result.get("poet") or "").strip()
            if should_block_theme(topic):
                logger.warning("Autonomous ML blocked flop theme: %r", topic[:40])
            if poet and should_block_poet(poet):
                logger.warning("Autonomous ML blocked flop poet: %r", poet[:40])
            if controls.get("best_caption_style"):
                result.setdefault("caption_style", controls["best_caption_style"])
            if controls.get("best_voice"):
                result.setdefault("voice", controls["best_voice"])
            if controls.get("best_publish_slots"):
                result.setdefault("publish_slots", controls["best_publish_slots"])
            if controls.get("best_hook_frame"):
                result.setdefault("hook_style", controls["best_hook_frame"])
        except Exception as exc:
            logger.warning("Autonomous reroute skipped: %s", exc)
        return result


# ── Backwards-compatible drop-in replacement for theme_fetcher ─────────────

def get_theme(exclude_recent: int = 400) -> dict:
    """Drop-in replacement for theme_fetcher.get_theme() with smart selection."""
    selector = SmartThemeSelector()
    result = selector.select()
    return {
        "topic": result["topic"],
        "series_number": 1,
        "series_title": result.get("series_title", f"Kalam #1: {result['topic'][:30]}"),
        "source": result.get("source", "smart"),
    }


if __name__ == "__main__":
    selector = SmartThemeSelector()
    for i in range(5):
        theme = selector.select()
        print(f"  {i+1}. {theme['topic']} (strategy: {theme['strategy']}, source: {theme['source']})")
