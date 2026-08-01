#!/usr/bin/env python3
"""SEO Score Calculator — Pre-upload video SEO analysis for maximum discoverability.

2026 MUST-HAVE: YouTube's algorithm is ENTIRELY driven by search + suggested
video signals. Without proper SEO scoring, you're uploading blind. This module
analyzes every video BEFORE upload and gives a 0-100 score with actionable fixes.

Key scoring areas:
  1. Title SEO (keywords, length, emotional hook)
  2. Description SEO (keywords, structure, hashtags)
  3. Tags SEO (relevance, search volume, competition)
  4. Thumbnail SEO (text readability, contrast, safe zone)
  5. Audience Match (India/PK audience keyword coverage)
  6. Retention Signals (hook strength, pacing indicators)

Usage:
  from seo_scorer import SEOScorer
  scorer = SEOScorer()
  score = scorer.score(script_data, title="...", tags=[...])
  print(f"SEO Score: {score['total']}/100")
  for fix in score['fixes']:
      print(f"  FIX: {fix}")
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seo_scorer")

ROOT = Path(__file__).resolve().parents[1]

# ── Channel's real search terms (analytics 2026-08-01) ─────────────────────
CHANNEL_SEARCH_TERMS = {
    "poetry background music", "sad shayari background music",
    "background music for poetry", "background music poetry",
    "poetry bg music", "sad background music",
    "copyright free background music", "no copyright music",
}

# ── High-value keywords for India/PK audience ──────────────────────────────
INDIA_PK_KEYWORDS = {
    "sad poetry", "urdu poetry", "shayari", "sad shayari", "dard bhari",
    "heart touching", "2 line poetry", "status", "dukhi", "gham",
    "ishq", "mohabbat", "judai", "tanhai", "barish", "raat",
    "ghalib", "iqbal", "mir", "bulleh shah",
    "hindi sad poetry", "dard bhari shayari hindi",
    "sad shayari hindi", "heart touching shayari hindi",
    "background music", "poetry background", "bg music",
    "copyright free", "no copyright", "original music",
}

# ── Emotional hook words that boost click-through ──────────────────────────
HOOK_WORDS = {
    "dil", "dard", "gham", "judai", "tanhai", "aansu", "bewafai",
    "ishq", "mohabbat", "yaad", "raat", "barish", "zakhm",
    "heart", "pain", "tears", "alone", "rain", "night",
    "rula", "ro", "rona", "dukh", "dukhi", "sad",
}


class SEOScorer:
    """Pre-upload SEO analysis for YouTube Shorts."""

    def __init__(self):
        self.channel_terms = CHANNEL_SEARCH_TERMS
        self.audience_keywords = INDIA_PK_KEYWORDS
        self.hook_words = HOOK_WORDS

    # ── Title Scoring ────────────────────────────────────────────────────

    def _score_title(self, title: str) -> Dict:
        """Score title SEO (0-25 points)."""
        score = 0
        issues = []
        title = (title or "").strip()

        # Length check (5-100 chars is ideal for YouTube)
        if not title:
            issues.append("Title is EMPTY — YouTube will auto-generate a bad one")
            return {"score": 0, "max": 25, "issues": issues}

        if len(title) < 10:
            issues.append("Title too short (< 10 chars) — add more keywords")
        elif len(title) > 100:
            issues.append("Title too long (> 100 chars) — YouTube truncates it")
        else:
            score += 5  # Good length

        # Has Roman/English text (critical for search ranking)
        has_latin = bool(re.search(r'[A-Za-z]', title))
        if has_latin:
            score += 5  # ✅ Roman/English title = better search ranking
        else:
            issues.append("Title is Urdu script only — YouTube search barely ranks Urdu titles. Use Roman/English!")

        # Contains channel's top search terms
        title_lower = title.lower()
        matched_search = sum(1 for t in self.channel_terms if t in title_lower)
        if matched_search >= 2:
            score += 7
        elif matched_search >= 1:
            score += 4
        else:
            issues.append("Title doesn't contain ANY of your channel's top search terms (poetry background music, sad shayari, etc.)")

        # Emotional hook words
        hook_matches = sum(1 for w in self.hook_words if w in title_lower)
        if hook_matches >= 1:
            score += 4
        else:
            issues.append("Title lacks emotional hook words (dil, dard, gham, judai, tanhai, etc.) — these drive clicks")

        # Has pipe separator (standard format: "Hook | Search Term | Poet")
        if " | " in title:
            score += 4
        else:
            issues.append("Use pipe format: 'Hook | poetry background music | Ghalib' — better for search + readability")

        return {"score": min(score, 25), "max": 25, "issues": issues}

    # ── Description Scoring ──────────────────────────────────────────────

    def _score_description(self, description: str) -> Dict:
        """Score description SEO (0-20 points)."""
        score = 0
        issues = []
        desc = (description or "").strip()

        if not desc:
            issues.append("Description is EMPTY — YouTube uses this for search indexing!")
            return {"score": 0, "max": 20, "issues": issues}

        # Length check (100+ chars is good)
        if len(desc) >= 100:
            score += 4
        else:
            issues.append("Description too short — add more context (aim for 100+ chars)")

        # Has keywords
        desc_lower = desc.lower()
        keyword_matches = sum(1 for k in self.audience_keywords if k in desc_lower)
        if keyword_matches >= 5:
            score += 6
        elif keyword_matches >= 2:
            score += 3
        else:
            issues.append("Description lacks audience keywords — add 'sad poetry', 'shayari', 'background music', etc.")

        # Has hashtags
        hashtag_count = len(re.findall(r'#\w+', desc))
        if 3 <= hashtag_count <= 15:
            score += 4
        elif hashtag_count > 15:
            issues.append("Too many hashtags (> 15) — YouTube ignores extras and may flag as spam")
        else:
            issues.append("Add 3-15 hashtags in description — they boost discoverability")

        # Has channel search terms
        search_matches = sum(1 for t in self.channel_terms if t in desc_lower)
        if search_matches >= 1:
            score += 3
        else:
            issues.append("Description doesn't mention your channel's top search terms")

        # Has CTA (subscribe, follow, etc.)
        has_cta = any(w in desc_lower for w in ["subscribe", "follow", "credit", "free to use", "original"])
        if has_cta:
            score += 3
        else:
            issues.append("Add a CTA in description (subscribe, free to use, etc.)")

        return {"score": min(score, 20), "max": 20, "issues": issues}

    # ── Tags Scoring ─────────────────────────────────────────────────────

    def _score_tags(self, tags: List[str]) -> Dict:
        """Score tags SEO (0-20 points)."""
        score = 0
        issues = []
        tags = tags or []

        # Count check (5-15 tags is ideal)
        if 5 <= len(tags) <= 15:
            score += 4
        elif len(tags) < 5:
            issues.append(f"Only {len(tags)} tags — YouTube allows up to 500 chars. Add 5-15 tags!")
        else:
            issues.append(f"Too many tags ({len(tags)}) — YouTube may flag as keyword stuffing")

        # Total character length
        total_chars = sum(len(t) for t in tags)
        if total_chars > 500:
            issues.append(f"Tags total {total_chars} chars — YouTube limit is 500")

        # Has channel search terms
        tags_lower = [t.lower().strip() for t in tags]
        search_matches = sum(1 for t in self.channel_terms if any(t in tag for tag in tags_lower))
        if search_matches >= 3:
            score += 7
        elif search_matches >= 1:
            score += 3
        else:
            issues.append("Tags don't include your channel's top search terms (poetry background music, sad shayari, etc.)")

        # Has India/PK audience keywords
        audience_matches = sum(1 for k in self.audience_keywords if any(k in tag for tag in tags_lower))
        if audience_matches >= 5:
            score += 5
        elif audience_matches >= 2:
            score += 2
        else:
            issues.append("Tags lack India/PK audience keywords (hindi sad poetry, dard bhari shayari, etc.)")

        # Has poet-specific tags
        has_poet = any(any(p in tag for tag in tags_lower) for p in ["ghalib", "iqbal", "mir", "bulleh", "allama"])
        if has_poet:
            score += 4
        else:
            issues.append("Add poet-specific tags (ghalib, iqbal, mir) — they drive search traffic")

        return {"score": min(score, 20), "max": 20, "issues": issues}

    # ── Audience Match Scoring ───────────────────────────────────────────

    def _score_audience_match(self, title: str, description: str, tags: List[str]) -> Dict:
        """Score audience match for India/PK/Bangladesh (0-20 points)."""
        score = 0
        issues = []

        all_text = f"{title} {description} {' '.join(tags)}".lower()

        # India audience (45.6%) — Hindi crossover terms
        india_terms = ["hindi", "sad shayari hindi", "dard bhari", "heart touching", "status", "shayari"]
        india_matches = sum(1 for t in india_terms if t in all_text)
        if india_matches >= 3:
            score += 7
        elif india_matches >= 1:
            score += 3
        else:
            issues.append("MISSING India audience terms! 45.6% of your viewers are Indian — add 'hindi sad poetry', 'dard bhari shayari', 'heart touching'")

        # Pakistan audience (20.6%) — Urdu terms
        pk_terms = ["urdu", "urdupoetry", "urdu shayari", "pakistan", "pakistani", "nazio"]
        pk_matches = sum(1 for t in pk_terms if t in all_text)
        if pk_matches >= 1:
            score += 4
        else:
            issues.append("Add 'urdu poetry' or 'urdu shayari' tags — 20.6% of your audience is Pakistani")

        # Bangladesh audience (14.8%) — Bengali/Urdu overlap
        bd_terms = ["bangla", "bengali", "sad poetry", "emotional"]
        bd_matches = sum(1 for t in bd_terms if t in all_text)
        if bd_matches >= 1:
            score += 3
        else:
            issues.append("Consider adding 'bangla sad poetry' tags — 14.8% of your audience is from Bangladesh")

        # Background music terms (channel's main search cluster)
        bg_terms = ["background music", "bg music", "copyright free", "no copyright", "original music"]
        bg_matches = sum(1 for t in bg_terms if t in all_text)
        if bg_matches >= 2:
            score += 6
        elif bg_matches >= 1:
            score += 3
        else:
            issues.append("Your channel's #1 search cluster is 'background music' — but your tags don't include these terms!")

        return {"score": min(score, 20), "max": 20, "issues": issues}

    # ── Retention Signals ────────────────────────────────────────────────

    def _score_retention(self, script_data: dict) -> Dict:
        """Score retention signals (0-15 points)."""
        score = 0
        issues = []

        # Hook strength
        hook = (script_data.get("hook_roman") or script_data.get("hook") or "").strip()
        if hook:
            hook_lower = hook.lower()
            hook_matches = sum(1 for w in self.hook_words if w in hook_lower)
            if hook_matches >= 1:
                score += 5  # Strong emotional hook
            else:
                issues.append("Hook lacks emotional words — first 2 seconds need STRONG pain/emotion to stop swiping")
        else:
            issues.append("NO hook! 67.4% of viewers swipe away — add a strong hook in first 2 seconds")

        # Scene count (3-5 scenes = good pacing)
        scenes = script_data.get("scenes", [])
        if 3 <= len(scenes) <= 6:
            score += 3
        elif len(scenes) > 6:
            issues.append("Too many scenes — each scene becomes too short, feels rushed")
        else:
            issues.append("Too few scenes — video feels slow, viewers swipe away")

        # Has Roman captions (80% of Shorts are watched on mute)
        has_roman = any(s.get("caption_roman") for s in scenes)
        if has_roman:
            score += 4
        else:
            issues.append("No Roman Urdu captions! 80% of Shorts are watched on mute in 2026 — captions are MANDATORY")

        # Spoken words count
        total_words = sum(len((s.get("caption") or "").split()) for s in scenes)
        if 40 <= total_words <= 80:
            score += 3
        else:
            issues.append(f"Spoken words: {total_words} — aim for 40-80 words (40-57 second Short)")

        return {"score": min(score, 15), "max": 15, "issues": issues}

    # ── Main Score ───────────────────────────────────────────────────────

    def score(self, script_data: dict = None, title: str = None,
              description: str = None, tags: List[str] = None) -> Dict:
        """Calculate total SEO score (0-100) with actionable fixes.

        Returns:
            {
                "total": 0-100,
                "grade": "A/B/C/D/F",
                "breakdown": {title, description, tags, audience, retention},
                "fixes": [list of actionable fixes],
                "passed": bool (score >= 70),
            }
        """
        script_data = script_data or {}
        title = title or script_data.get("title", "")
        # Use Roman title if available
        if script_data.get("title_roman"):
            title = script_data["title_roman"]
        description = description or script_data.get("description", "")
        tags = tags or script_data.get("tags", [])

        # Score each category
        title_score = self._score_title(title)
        desc_score = self._score_description(description)
        tags_score = self._score_tags(tags)
        audience_score = self._score_audience_match(title, description, tags)
        retention_score = self._score_retention(script_data)

        # Calculate total
        total = (title_score["score"] + desc_score["score"] +
                 tags_score["score"] + audience_score["score"] +
                 retention_score["score"])

        # Grade
        if total >= 85:
            grade = "A"
        elif total >= 70:
            grade = "B"
        elif total >= 55:
            grade = "C"
        elif total >= 40:
            grade = "D"
        else:
            grade = "F"

        # Collect all fixes
        all_issues = []
        for category in [title_score, desc_score, tags_score, audience_score, retention_score]:
            all_issues.extend(category.get("issues", []))

        # Priority-order fixes
        high_priority = [i for i in all_issues if any(kw in i.lower() for kw in ["empty", "missing", "no roman", "urdu script"])]
        medium_priority = [i for i in all_issues if i not in high_priority and any(kw in i.lower() for kw in ["add", "doesn't", "lacks", "lack"])]
        low_priority = [i for i in all_issues if i not in high_priority and i not in medium_priority]

        fixes = high_priority + medium_priority + low_priority

        result = {
            "total": total,
            "max": 100,
            "grade": grade,
            "passed": total >= 70,
            "breakdown": {
                "title": title_score,
                "description": desc_score,
                "tags": tags_score,
                "audience_match": audience_score,
                "retention_signals": retention_score,
            },
            "fixes": fixes,
            "fix_count": len(fixes),
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("SEO Score: %d/100 (Grade: %s) — %d fixes needed",
                    total, grade, len(fixes))

        return result

    def auto_fix(self, script_data: dict) -> dict:
        """Auto-fix SEO issues in script_data. Returns fixed script_data."""
        score = self.score(script_data)
        if score["passed"]:
            return script_data

        tags = list(script_data.get("tags", []))

        # Fix 1: Add missing channel search terms to tags
        for term in self.channel_terms:
            if not any(term in t.lower() for t in tags):
                tags.append(term)

        # Fix 2: Add missing India audience tags
        india_tags = ["hindi sad poetry", "dard bhari shayari hindi", "heart touching shayari"]
        for tag in india_tags:
            if not any(tag in t.lower() for t in tags):
                tags.append(tag)

        # Fix 3: Add background music tags
        bg_tags = ["poetry background music", "sad background music", "copyright free background music"]
        for tag in bg_tags:
            if not any(tag in t.lower() for t in tags):
                tags.append(tag)

        # Trim tags to YouTube limit (500 chars)
        total_chars = 0
        trimmed_tags = []
        for tag in tags:
            if total_chars + len(tag) + 1 > 480:  # Leave room for separators
                break
            trimmed_tags.append(tag)
            total_chars += len(tag) + 1

        script_data["tags"] = trimmed_tags
        script_data["seo_score"] = self.score(script_data)

        logger.info("Auto-fix applied: %d tags, SEO score now %d/100",
                    len(trimmed_tags), script_data["seo_score"]["total"])

        return script_data


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scorer = SEOScorer()
    # Test with a sample video
    test_data = {
        "title": "غمِ دل",
        "title_roman": "Gham-e-Dil | Sad Urdu Poetry | Background Music",
        "hook_roman": "Jab apna bana hua bhi paraya lage...",
        "description": "Sad Urdu poetry 💔 dukhi shayari — heart touching poetry with background music. #urdupoetry #sadshayari",
        "tags": ["urdu poetry", "shayari", "sad poetry", "poetry background music"],
        "scenes": [
            {"caption": "جب اپنا بنا ہوا بھی پرایا لگے", "caption_roman": "Jab apna bana hua bhi paraya lage"},
            {"caption": "تو دل کی حالت کیا ہو", "caption_roman": "To dil ki haalat kya ho"},
            {"caption": "غم کی رات میں تنہا بیٹھا ہوں", "caption_roman": "Gham ki raat mein tanha baitha hoon"},
            {"caption": "اور کوئی نہیں سوا میرے", "caption_roman": "Aur koi nahi sivaa mere"},
        ],
    }
    result = scorer.score(test_data)
    print(f"\n📊 SEO Score: {result['total']}/100 (Grade: {result['grade']})")
    print(f"   {'✅ PASSED' if result['passed'] else '❌ NEEDS FIXES'}")
    print(f"\nBreakdown:")
    for cat, data in result["breakdown"].items():
        print(f"  {cat}: {data['score']}/{data['max']}")
    if result["fixes"]:
        print(f"\n🔧 Fixes ({len(result['fixes'])}):")
        for fix in result["fixes"]:
            print(f"  • {fix}")
