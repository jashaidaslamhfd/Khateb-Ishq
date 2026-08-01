#!/usr/bin/env python3
"""Monetization Tracker — Track YouTube Partner Program progress in real-time.

2026 MUST-HAVE: YouTube now has TWO monetization tiers:
  - Expanded YPP: 500 subs + 3,000 watch hours OR 3M Shorts views
  - Full YPP: 1,000 subs + 4,000 watch hours OR 10M Shorts views

This module tracks progress toward both tiers and calculates:
  1. How many days until monetization (based on current growth rate)
  2. What content mix is needed (Shorts vs Long videos)
  3. Revenue projections once monetized
  4. Daily/weekly/monthly growth targets

Usage:
  from monetization_tracker import MonetizationTracker
  tracker = MonetizationTracker()
  status = tracker.get_status()
  print(f"Days to monetization: {status['days_to_full_ypp']}")
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("monetization_tracker")

ROOT = Path(__file__).resolve().parents[1]
TRACKER_PATH = ROOT / "data" / "monetization_tracker.json"

# ── YouTube Partner Program Requirements (2026) ────────────────────────────
EXPANDED_YPP = {
    "name": "Expanded YPP",
    "subscribers": 500,
    "watch_hours": 3000,
    "shorts_views": 3_000_000,
    "period_days": 90,
    "unlocks": ["Super Chat", "Super Thanks", "Channel Memberships", "Merchandise"],
}

FULL_YPP = {
    "name": "Full YPP",
    "subscribers": 1000,
    "watch_hours": 4000,
    "shorts_views": 10_000_000,
    "period_days": 365,
    "unlocks": ["Ad revenue (45%)", "YouTube Premium revenue", "Shopping affiliate"],
}


class MonetizationTracker:
    """Track YouTube Partner Program progress."""

    def __init__(self):
        self.channel_stats = self._load_stats()

    def _load_stats(self) -> dict:
        """Load channel stats from tracker file or history."""
        try:
            return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Default stats from real data (2026-08-01)
            return {
                "subscribers": 2134,
                "watch_hours": 509,
                "shorts_views_90d": 633,
                "retention_rate": 0.326,
                "swipe_away_rate": 0.674,
                "audience": {
                    "india": 0.456,
                    "pakistan": 0.206,
                    "bangladesh": 0.148,
                    "other": 0.190,
                },
                "growth_rate": {
                    "subs_per_day": 2.0,
                    "watch_hours_per_day": 5.0,
                    "shorts_views_per_day": 7.0,
                },
                "last_updated": None,
            }

    def _save_stats(self) -> None:
        TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.channel_stats["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = TRACKER_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.channel_stats, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(TRACKER_PATH)

    def update_stats(self, subscribers: int = None, watch_hours: float = None,
                     shorts_views: int = None, retention_rate: float = None) -> dict:
        """Update channel stats with latest data."""
        if subscribers is not None:
            self.channel_stats["subscribers"] = subscribers
        if watch_hours is not None:
            self.channel_stats["watch_hours"] = watch_hours
        if shorts_views is not None:
            self.channel_stats["shorts_views_90d"] = shorts_views
        if retention_rate is not None:
            self.channel_stats["retention_rate"] = retention_rate
            self.channel_stats["swipe_away_rate"] = 1.0 - retention_rate

        self._save_stats()
        return self.get_status()

    def get_status(self) -> dict:
        """Get full monetization status with projections."""
        subs = self.channel_stats.get("subscribers", 0)
        watch_hours = self.channel_stats.get("watch_hours", 0)
        shorts_views = self.channel_stats.get("shorts_views_90d", 0)
        retention = self.channel_stats.get("retention_rate", 0.326)
        growth = self.channel_stats.get("growth_rate", {})

        subs_per_day = growth.get("subs_per_day", 2.0)
        watch_hours_per_day = growth.get("watch_hours_per_day", 5.0)
        shorts_views_per_day = growth.get("shorts_views_per_day", 7.0)

        # ── Expanded YPP Progress ──────────────────────────────────────
        expanded_subs_done = subs >= EXPANDED_YPP["subscribers"]
        expanded_wh_done = watch_hours >= EXPANDED_YPP["watch_hours"]
        expanded_sv_done = shorts_views >= EXPANDED_YPP["shorts_views"]
        expanded_wh_progress = min(1.0, watch_hours / EXPANDED_YPP["watch_hours"])
        expanded_sv_progress = min(1.0, shorts_views / EXPANDED_YPP["shorts_views"])

        # ── Full YPP Progress ──────────────────────────────────────────
        full_subs_done = subs >= FULL_YPP["subscribers"]
        full_wh_done = watch_hours >= FULL_YPP["watch_hours"]
        full_sv_done = shorts_views >= FULL_YPP["shorts_views"]
        full_wh_progress = min(1.0, watch_hours / FULL_YPP["watch_hours"])
        full_sv_progress = min(1.0, shorts_views / FULL_YPP["shorts_views"])

        # ── Days to Monetization ───────────────────────────────────────
        # Path 1: Watch Hours (most realistic for this channel)
        wh_needed = max(0, FULL_YPP["watch_hours"] - watch_hours)
        if watch_hours_per_day > 0:
            days_to_wh = wh_needed / watch_hours_per_day
        else:
            days_to_wh = float("inf")

        # Path 2: Shorts Views (very hard)
        sv_needed = max(0, FULL_YPP["shorts_views"] - shorts_views)
        if shorts_views_per_day > 0:
            days_to_sv = sv_needed / shorts_views_per_day
        else:
            days_to_sv = float("inf")

        # Best path
        best_path = "watch_hours" if days_to_wh < days_to_sv else "shorts_views"
        days_to_full = min(days_to_wh, days_to_sv)

        # ── Content Mix Recommendation ─────────────────────────────────
        content_mix = self._calculate_content_mix(watch_hours, wh_needed, retention)

        # ── Revenue Projection ─────────────────────────────────────────
        revenue_projection = self._project_revenue(subs, watch_hours)

        # ── Retention Impact ───────────────────────────────────────────
        retention_impact = self._calculate_retention_impact(retention)

        return {
            "current_stats": {
                "subscribers": subs,
                "watch_hours": watch_hours,
                "shorts_views_90d": shorts_views,
                "retention_rate": f"{retention * 100:.1f}%",
                "swipe_away_rate": f"{(1 - retention) * 100:.1f}%",
            },
            "expanded_ypp": {
                "subscribers_met": expanded_subs_done,
                "watch_hours_progress": f"{expanded_wh_progress * 100:.1f}%",
                "shorts_views_progress": f"{expanded_sv_progress * 100:.1f}%",
                "watch_hours_met": expanded_wh_done,
                "shorts_views_met": expanded_sv_done,
                "qualified": expanded_subs_done and (expanded_wh_done or expanded_sv_done),
                "unlocks": EXPANDED_YPP["unlocks"],
            },
            "full_ypp": {
                "subscribers_met": full_subs_done,
                "watch_hours_progress": f"{full_wh_progress * 100:.1f}%",
                "shorts_views_progress": f"{full_sv_progress * 100:.1f}%",
                "watch_hours_needed": wh_needed,
                "shorts_views_needed": sv_needed,
                "watch_hours_met": full_wh_done,
                "shorts_views_met": full_sv_done,
                "qualified": full_subs_done and (full_wh_done or full_sv_done),
                "unlocks": FULL_YPP["unlocks"],
            },
            "projections": {
                "best_path": best_path,
                "days_to_full_ypp": round(days_to_full) if days_to_full != float("inf") else None,
                "estimated_date": (datetime.now(timezone.utc) + timedelta(days=days_to_full)).strftime("%Y-%m-%d")
                    if days_to_full != float("inf") else "N/A",
                "at_current_rate": f"~{days_to_full:.0f} days" if days_to_full < 365 else "1+ year",
            },
            "content_mix": content_mix,
            "revenue_projection": revenue_projection,
            "retention_impact": retention_impact,
            "action_items": self._generate_action_items(watch_hours, retention, days_to_full),
        }

    def _calculate_content_mix(self, current_wh: float, wh_needed: float,
                                retention: float) -> dict:
        """Calculate the optimal content mix for monetization."""
        # Each long mix (8-10 min) = ~66.7 watch hours per 500 views
        # Each poetry short = ~0.5 watch hours per 100 views
        # At current retention (32.6%), we need more content to compensate

        retention_factor = max(0.5, retention / 0.5)  # 50% retention = 1.0x

        # Calculate needed long mixes
        long_mix_hours = 66.7 * retention_factor  # Adjusted for retention
        long_mixes_needed = max(0, int(wh_needed / long_mix_hours))

        # At 2 long mixes/day, how many days?
        days_for_mixes = long_mixes_needed / 2 if long_mixes_needed > 0 else 0

        return {
            "daily_long_mixes": 2,
            "daily_poetry_shorts": 2,
            "daily_music_shorts": 1,
            "long_mixes_needed": long_mixes_needed,
            "days_for_mixes": round(days_for_mixes),
            "estimated_watch_hours_per_mix": round(long_mix_hours, 1),
            "retention_impact": f"Retention at {retention*100:.1f}% = {retention_factor:.2f}x watch hours multiplier",
            "recommendation": "2 long mixes/day + 2 poetry shorts/day = ~4,000 watch hours in ~30 days" if retention >= 0.3
                else "FIX RETENTION FIRST! 67.4% swipe-away means algorithm won't push your videos",
        }

    def _project_revenue(self, subs: int, watch_hours: float) -> dict:
        """Project revenue once monetized."""
        # YouTube Shorts RPM: ~$0.01-0.03 per view (India/PK audience = lower RPM)
        # Long video RPM: ~$1-3 per 1,000 views
        # With 45.6% India audience, RPM is lower

        # Conservative estimates
        shorts_rpm = 0.015  # $ per 1,000 views
        long_rpm = 1.5  # $ per 1,000 views

        # Monthly projections (post-monetization)
        monthly_shorts_views = 100_000  # Conservative
        monthly_long_views = 10_000  # Conservative

        monthly_shorts_revenue = monthly_shorts_views * shorts_rpm / 1000
        monthly_long_revenue = monthly_long_views * long_rpm / 1000

        return {
            "shorts_rpm": f"${shorts_rpm}/1000 views",
            "long_rpm": f"${long_rpm}/1000 views",
            "projected_monthly_shorts_revenue": f"${monthly_shorts_revenue:.2f}",
            "projected_monthly_long_revenue": f"${monthly_long_revenue:.2f}",
            "projected_monthly_total": f"${monthly_shorts_revenue + monthly_long_revenue:.2f}",
            "note": "India/PK audience = lower RPM. Revenue grows with views.",
            "growth_path": "1. Monetize → 2. Daily content → 3. 100K views/month → 4. $50-100/month",
        }

    def _calculate_retention_impact(self, retention: float) -> dict:
        """Calculate how retention affects reach and monetization."""
        # YouTube's algorithm: higher retention = more reach
        # At 32.6% retention, algorithm throttles reach
        # At 50%+, algorithm starts pushing videos

        current_reach = retention * 2  # Simplified multiplier
        target_retention = 0.50
        target_reach = target_retention * 2

        return {
            "current_retention": f"{retention * 100:.1f}%",
            "target_retention": f"{target_retention * 100:.0f}%",
            "current_reach_multiplier": f"{current_reach:.2f}x",
            "target_reach_multiplier": f"{target_reach:.2f}x",
            "reach_increase_if_fixed": f"+{(target_reach / current_reach - 1) * 100:.0f}%",
            "impact": "Every 1% retention increase = 10-15% more algorithm reach",
            "critical": retention < 0.40,
            "message": "🔴 CRITICAL: 67.4% swipe-away = algorithm kills your reach. Fix retention FIRST!"
                if retention < 0.40
                else "🟡 Retention is improving — keep optimizing hooks and pacing",
        }

    def _generate_action_items(self, watch_hours: float, retention: float,
                                days_to_full: float) -> List[str]:
        """Generate prioritized action items."""
        items = []

        if retention < 0.40:
            items.append("🔴 P0: Fix retention (currently 32.6% → target 50%+). Without this, NOTHING works!")
            items.append("  → Hook overlay (first 2 seconds) — IMPLEMENTED")
            items.append("  → Faster pacing (2-3 sec cuts) — IMPLEMENTED")
            items.append("  → Loop trick (end connects to start) — IMPLEMENTED")
            items.append("  → Test with real uploads and measure retention change")

        if watch_hours < 4000:
            items.append("🔴 P0: Start daily long mix videos (2/day) for watch hours")
            items.append(f"  → Need {4000 - watch_hours:.0f} more watch hours")
            items.append("  → Each long mix = ~66.7 hours per 500 views")
            items.append(f"  → At 2/day: ~{days_to_full:.0f} days to monetization")

        if days_to_full > 60:
            items.append("🟡 P1: Increase daily content output")
            items.append("  → 2 long mixes + 2 poetry shorts + 1 music short per day")

        items.append("🟡 P1: Target India audience (45.6%) with Hindi crossover tags")
        items.append("🟢 P2: Multi-platform posting (TikTok, IG Reels) for cross-promotion")
        items.append("🟢 P2: Community posts for engagement (keeps subscribers active)")

        return items


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tracker = MonetizationTracker()
    status = tracker.get_status()

    print("\n📊 MONETIZATION STATUS")
    print("=" * 50)
    print(f"Subscribers: {status['current_stats']['subscribers']}")
    print(f"Watch Hours: {status['current_stats']['watch_hours']}")
    print(f"Shorts Views: {status['current_stats']['shorts_views_90d']}")
    print(f"Retention: {status['current_stats']['retention_rate']}")
    print(f"Swipe Away: {status['current_stats']['swipe_away_rate']}")

    print(f"\n📈 FULL YPP PROGRESS")
    print(f"Subscribers: {'✅' if status['full_ypp']['subscribers_met'] else '❌'}")
    print(f"Watch Hours: {status['full_ypp']['watch_hours_progress']}")
    print(f"Shorts Views: {status['full_ypp']['shorts_views_progress']}")
    print(f"Watch Hours Needed: {status['full_ypp']['watch_hours_needed']}")

    print(f"\n⏱️ PROJECTIONS")
    print(f"Best Path: {status['projections']['best_path']}")
    print(f"Days to Monetization: {status['projections']['days_to_full_ypp']}")
    print(f"Estimated Date: {status['projections']['estimated_date']}")

    print(f"\n🎬 CONTENT MIX")
    print(f"Daily Long Mixes: {status['content_mix']['daily_long_mixes']}")
    print(f"Long Mixes Needed: {status['content_mix']['long_mixes_needed']}")
    print(f"Days for Mixes: {status['content_mix']['days_for_mixes']}")
    print(f"Recommendation: {status['content_mix']['recommendation']}")

    print(f"\n💰 REVENUE PROJECTION")
    print(f"Monthly Total: {status['revenue_projection']['projected_monthly_total']}")
    print(f"Growth Path: {status['revenue_projection']['growth_path']}")

    print(f"\n🔧 ACTION ITEMS")
    for item in status["action_items"]:
        print(f"  {item}")
