#!/usr/bin/env python3
"""30-Day Monetization War Plan — Aggressive strategy to reach 4,000 watch hours.

REALITY CHECK (2026-08-01):
  - 2,134 subs ✅ (already past 1,000)
  - 509 watch hours ❌ (need 3,491 more)
  - 32.6% retention ❌ (need 50%+ for algorithm push)
  - 67.4% swipe away ❌ (algorithm kills reach)

MATH:
  - 2 long mixes/day × 30 days = 60 mixes
  - At 50% retention: 400 views × 5 min = 33.3h/mix = 2,000h total ❌
  - At 60% retention: 800 views × 6 min = 80h/mix = 4,800h total ✅
  - CONCLUSION: Retention MUST reach 55%+ for monetization in 30 days

STRATEGY:
  - Week 1: Fix retention + start 3 long mixes/day
  - Week 2: Volume push + SEO optimization
  - Week 3: Algorithm push + engagement
  - Week 4: Final sprint

DAILY CONTENT OUTPUT:
  - 3 long mixes (8-10 min) = primary watch hours
  - 2 poetry shorts = daily algorithm engagement
  - 1 music short = search traffic
  - Total: 6 videos/day = 180 videos in 30 days
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "30_day_war_plan.json"

# ── DAILY CONTENT SCHEDULE ─────────────────────────────────────────────────
# 3 long mixes + 2 poetry shorts + 1 music short = 6 videos/day
# Total: 180 videos in 30 days

DAILY_SCHEDULE = [
    {
        "time": "04:00 PKT",   # UTC 23:00 previous day
        "type": "long_mix",
        "duration": "8-10 min",
        "purpose": "Watch hours (primary)",
        "title_template": "Sad Poetry Mix #{n} | Heart Touching Shayari | Background Music",
        "workflow": "daily_mix.yml",
    },
    {
        "time": "09:00 PKT",   # UTC 04:00
        "type": "poetry_short",
        "duration": "40-57 sec",
        "purpose": "Algorithm engagement + daily content",
        "title_template": "{hook} | Sad Urdu Poetry | poetry background music",
        "workflow": "main.yml",
    },
    {
        "time": "13:00 PKT",   # UTC 08:00
        "type": "long_mix",
        "duration": "8-10 min",
        "purpose": "Watch hours (primary)",
        "title_template": "Dard Bhari Shayari Mix #{n} | Sad Background Music | Poetry BG Music",
        "workflow": "daily_mix.yml",
    },
    {
        "time": "15:00 PKT",   # UTC 10:00
        "type": "poetry_short",
        "duration": "40-57 sec",
        "purpose": "Algorithm engagement + peak hours",
        "title_template": "{hook} | Emotional Poetry | sad shayari background music",
        "workflow": "main.yml",
    },
    {
        "time": "18:00 PKT",   # UTC 13:00
        "type": "music_short",
        "duration": "1-2 min",
        "purpose": "Search traffic (background music cluster)",
        "title_template": "Sad Background Music | Copyright Free | Original #{n}",
        "workflow": "sad_music.yml",
    },
    {
        "time": "21:00 PKT",   # UTC 16:00
        "type": "long_mix",
        "duration": "8-10 min",
        "purpose": "Watch hours (evening peak)",
        "title_template": "Emotional Poetry Mix #{n} | Background Music for Poetry | Heart Touching",
        "workflow": "daily_mix.yml",
    },
]

# ── RETENTION FIX PROTOCOL ─────────────────────────────────────────────────
# Current: 32.6% stay / 67.4% swipe away
# Target: 55%+ stay / <45% swipe away
# This is the #1 priority. Without this, NOTHING works.

RETENTION_FIXES = {
    "hook_overlay": {
        "status": "IMPLEMENTED",
        "description": "Big bold yellow text in first 2.5 seconds",
        "expected_impact": "+10-15% retention",
        "code": "video_editor.py HOOK_OVERLAY=1",
    },
    "fast_cut": {
        "status": "IMPLEMENTED",
        "description": "Each scene = 2 punch-cuts with alt pan/zoom",
        "expected_impact": "+5-8% retention",
        "code": "video_editor.py FAST_CUT=1",
    },
    "cinematic_grade": {
        "status": "IMPLEMENTED",
        "description": "Warm contrast + vignette + film grain",
        "expected_impact": "+3-5% retention",
        "code": "video_editor.py APPLY_GRADE=1",
    },
    "roman_captions": {
        "status": "IMPLEMENTED",
        "description": "On-screen captions in Roman Urdu (80% watch on mute)",
        "expected_impact": "+5-10% retention",
        "code": "video_editor.py CAPTION_SCRIPT=roman",
    },
    "loop_trick": {
        "status": "IMPLEMENTED",
        "description": "Last scene connects back to first hook",
        "expected_impact": "+2-5% retention (rewatch)",
        "code": "video_editor.py LOOP_TRICK=1",
    },
    "emotional_music": {
        "status": "IMPLEMENTED",
        "description": "Cinematic violin + cello + strings + reverb",
        "expected_impact": "+3-5% retention",
        "code": "generate_music_beds.py",
    },
    "total_expected": "+28-48% retention boost",
    "current": "32.6%",
    "target": "55%+",
    "note": "These are additive. Hook overlay alone should push 32.6% → 45%+. Combined = 55%+.",
}

# ── SEO STRATEGY (every video must rank) ───────────────────────────────────
# Without search ranking, videos get 0 organic views.
# Channel's top search terms drive 87.9% of traffic.

SEO_STRATEGY = {
    "title_format": "Roman Hook | Search Term | Poet",
    "title_examples": [
        "Gham-e-Dil | Sad Urdu Poetry | Background Music | Ghalib",
        "Jab Apna Bana Hua | Sad Shayari Background Music | Poetry BG Music",
        "Dard Bhari Shayari | Poetry Background Music | Heart Touching",
        "Tanhai Ki Raat | Background Music for Poetry | Copyright Free",
        "Bewafai Ka Dard | Sad Background Music | Emotional Poetry",
    ],
    "must_include_terms": [
        # Channel's top 8 search terms (must appear in title or tags)
        "poetry background music",
        "sad shayari background music",
        "background music for poetry",
        "poetry bg music",
        "sad background music",
        "copyright free background music",
        "no copyright music",
        "background music poetry",
    ],
    "india_audience_tags": [
        # 45.6% of viewers are Indian — Hindi crossover terms
        "hindi sad poetry",
        "dard bhari shayari hindi",
        "sad shayari hindi",
        "heart touching shayari hindi",
        "sad status hindi",
        "dukhi status",
    ],
    "description_template": """🎵 {title} — Khateb-e-Ishq

Sad Urdu poetry status 💔 dukhi shayari — heart touching 2 line poetry with AI Urdu narration.

Ye shayari aapke dil ki baat keh rahi hai ❤️ Sunte rahiye...

📌 SUBSCRIBE for daily sad poetry with background music
🎵 Music: 100% Original & Copyright-Free (Khateb-e-Ishq composition)
✅ Free to use with credit: 'Music: Khateb-e-Ishq (YouTube)'

#poetrybackgroundmusic #sadshayaribackgroundmusic #backgroundmusicforpoetry
#poetrybgmusic #sadbackgroundmusic #copyrightfreebackgroundmusic
#nocopyrightmusic #urdupoetry #sadpoetry #shayari""",
}

# ── 30-DAY WEEKLY PLAN ─────────────────────────────────────────────────────

WEEKLY_PLAN = {
    "week_1": {
        "days": "Day 1-7",
        "focus": "RETENTION FIX + LAUNCH",
        "daily_content": 6,
        "expected_watch_hours": 200,
        "actions": [
            "✅ Hook overlay ACTIVE on every video",
            "✅ Fast cuts + cinematic grade ACTIVE",
            "✅ Roman captions ACTIVE",
            "✅ Loop trick ACTIVE",
            "✅ 3 long mixes/day starting Day 1",
            "✅ SEO scorer auto-fix on every upload",
            "✅ Thumbnail A/B testing on every video",
            "📊 Monitor retention after 48 hours",
            "📊 If retention < 45%, adjust hook text",
        ],
        "milestone": "Retention should improve to 45%+ by Day 7",
    },
    "week_2": {
        "days": "Day 8-14",
        "focus": "VOLUME + SEO PUSH",
        "daily_content": 6,
        "expected_watch_hours": 600,
        "actions": [
            "📈 Check retention data — adjust if needed",
            "🔍 SEO optimization on ALL videos",
            "📝 SRT subtitles on every video",
            "🏷️ A/B test title formats",
            "💬 AI comment responder on every video",
            "📱 Community posts daily",
            "🎯 Target India audience with Hindi tags",
        ],
        "milestone": "Retention should be 50%+ by Day 14",
    },
    "week_3": {
        "days": "Day 15-21",
        "focus": "ALGORITHM PUSH",
        "daily_content": 6,
        "expected_watch_hours": 1200,
        "actions": [
            "🚀 Algorithm should start pushing videos",
            "📈 Views should increase 2-3x",
            "🎯 Focus on long mix titles with search terms",
            "📊 Track which themes get most views",
            "🔄 Double down on winning themes",
            "💬 Engage with every comment within 1 hour",
            "📱 Cross-post to TikTok/IG if enabled",
        ],
        "milestone": "Watch hours should be ~2,000 by Day 21",
    },
    "week_4": {
        "days": "Day 22-30",
        "focus": "FINAL SPRINT",
        "daily_content": 6,
        "expected_watch_hours": 1500,
        "actions": [
            "🏃 Maximum content output",
            "📊 Check monetization progress daily",
            "🎯 Focus on search-optimized long mixes",
            "💬 Maximum engagement on every video",
            "📢 Community posts for subscriber growth",
            "🔔 Remind subscribers to turn on notifications",
            "📈 Track watch hours progress",
        ],
        "milestone": "4,000 watch hours = MONETIZATION! 🎉",
    },
}

# ── WATCH HOURS PROJECTION ─────────────────────────────────────────────────

def project_watch_hours():
    """Project watch hours over 30 days based on retention scenarios."""
    current_wh = 509
    target_wh = 4000

    # Long mix parameters
    mixes_per_day = 3
    short_views_per_day = 2
    music_shorts_per_day = 1

    projections = {}
    for retention_pct, label in [(35, "pessimistic"), (45, "moderate"), (55, "optimistic"), (60, "viral")]:
        # Views increase with retention (algorithm pushes more)
        base_views = 100 + retention_pct * 5  # 275, 325, 375, 400
        avg_watch_pct = retention_pct / 100  # 0.35, 0.45, 0.55, 0.60

        daily_wh = 0
        for day in range(1, 31):
            # Views grow over time as algorithm pushes more
            growth_factor = 1.0 + (day / 30) * 0.5  # 1.0 → 1.5 over 30 days
            views = base_views * growth_factor

            # Long mix watch hours
            mix_wh = views * (8 * avg_watch_pct) / 60 * mixes_per_day
            # Short watch hours
            short_wh = views * 0.3 * (0.5 * avg_watch_pct) / 60 * short_views_per_day
            # Music short watch hours
            music_wh = views * 0.2 * (1.5 * avg_watch_pct) / 60 * music_shorts_per_day

            daily_wh += mix_wh + short_wh + music_wh

        total_wh = current_wh + daily_wh
        projections[label] = {
            "retention": f"{retention_pct}%",
            "total_30_day_wh": round(daily_wh),
            "total_with_current": round(total_wh),
            "monetized": total_wh >= target_wh,
            "gap": round(max(0, target_wh - total_wh)),
        }

    return projections


def generate_war_plan():
    """Generate the complete 30-day war plan."""
    projections = project_watch_hours()

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_stats": {
            "subscribers": 2134,
            "watch_hours": 509,
            "retention": "32.6%",
            "swipe_away": "67.4%",
            "needed_watch_hours": 3491,
        },
        "daily_schedule": DAILY_SCHEDULE,
        "retention_fixes": RETENTION_FIXES,
        "seo_strategy": SEO_STRATEGY,
        "weekly_plan": WEEKLY_PLAN,
        "projections": projections,
        "critical_insight": "Retention is EVERYTHING. At 32.6%, algorithm kills reach. At 55%+, algorithm pushes. Fix retention FIRST.",
        "success_probability": {
            "without_retention_fix": "5% — algorithm will not push videos",
            "with_retention_fix_45pct": "30% — good but may need more time",
            "with_retention_fix_55pct": "70% — algorithm will push, monetization likely",
            "with_retention_fix_60pct": "90% — viral territory, monetization almost certain",
        },
    }

    # Save plan
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PLAN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PLAN_PATH)

    return plan


if __name__ == "__main__":
    plan = generate_war_plan()

    print("\n🔥 30-DAY MONETIZATION WAR PLAN")
    print("=" * 60)
    print(f"Current: {plan['current_stats']['subscribers']} subs, {plan['current_stats']['watch_hours']} watch hours")
    print(f"Need: {plan['current_stats']['needed_watch_hours']} more watch hours")
    print(f"Retention: {plan['current_stats']['retention']} (CRITICAL: need 55%+)")
    print()

    print("📊 RETENTION FIXES:")
    for fix, data in plan["retention_fixes"].items():
        if isinstance(data, dict) and "status" in data:
            status = "✅" if data["status"] == "IMPLEMENTED" else "❌"
            print(f"  {status} {fix}: {data['description']} ({data['expected_impact']})")
    print()

    print("📊 30-DAY PROJECTIONS:")
    for label, data in plan["projections"].items():
        status = "✅ MONETIZED!" if data["monetized"] else f"❌ {data['gap']}h short"
        print(f"  {label.upper()} ({data['retention']} retention): {data['total_with_current']}h {status}")
    print()

    print("📅 DAILY SCHEDULE (6 videos/day):")
    for slot in plan["daily_schedule"]:
        print(f"  {slot['time']}: {slot['type']} ({slot['duration']}) — {slot['purpose']}")
    print()

    print("🎯 SUCCESS PROBABILITY:")
    for scenario, prob in plan["success_probability"].items():
        print(f"  {scenario}: {prob}")
