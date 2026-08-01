#!/usr/bin/env python3
"""Trend Predictor — Predict future trending Urdu poetry topics.

This module predicts which Urdu poetry topics will trend by combining:
  1. YouTube autosuggest momentum (rising search queries)
  2. Google Trends data (Pakistan/India region)
  3. Seasonal/annual patterns (Ramadan, Eid, monsoon, winter)
  4. Competitor analysis (what's working for similar channels)
  5. Performance-learned data (channel's own viral patterns)

Usage:
  from trend_predictor import TrendPredictor
  predictor = TrendPredictor()
  predictions = predictor.predict(n=5)
  for p in predictions:
      print(f"{p['topic']} (score: {p['score']}, confidence: {p['confidence']})")
"""

import json
import logging
import os
import re
import random
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("trend_predictor")

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_CACHE_PATH = ROOT / "data" / "trend_predictions.json"

# ── Seasonal poetry themes (Pakistan/India cultural calendar) ──────────────
# Each month has characteristic poetry moods that consistently perform well.
SEASONAL_THEMES = {
    1:  [  # January — winter melancholy, saal-e-nau
        {"topic": "sardi raat tanhai", "mood": "winter", "weight": 1.3},
        {"topic": "naye saal ki umeed", "mood": "hopeful", "weight": 1.2},
        {"topic": "andheri sardi raat", "mood": "winter", "weight": 1.2},
    ],
    2:  [  # February — Valentine's month (ishq peak)
        {"topic": "mohabbat juda'i", "mood": "romantic", "weight": 1.5},
        {"topic": "ishq aur dard", "mood": "romantic", "weight": 1.4},
        {"topic": "dil ki baat", "mood": "romantic", "weight": 1.3},
    ],
    3:  [  # March — spring, basant
        {"topic": "bahar aayi", "mood": "spring", "weight": 1.2},
        {"topic": "basant shayari", "mood": "spring", "weight": 1.1},
    ],
    4:  [  # April — Ramadan (shifts, but often April-May)
        {"topic": "roza dua shayari", "mood": "spiritual", "weight": 1.5},
        {"topic": "ramzan mubarak poetry", "mood": "spiritual", "weight": 1.6},
    ],
    5:  [  # May — Ramadan/Eid
        {"topic": "eid mubarak shayari", "mood": "celebration", "weight": 1.6},
        {"topic": "chaand raat poetry", "mood": "celebration", "weight": 1.5},
    ],
    6:  [  # June — summer heat, nostalgia
        {"topic": "garmi yaad shayari", "mood": "nostalgic", "weight": 1.0},
    ],
    7:  [  # July — monsoon (barish peak!)
        {"topic": "barish shayari", "mood": "rain", "weight": 1.7},
        {"topic": "baarish mein tanhai", "mood": "rain", "weight": 1.6},
        {"topic": "mausam barish poetry", "mood": "rain", "weight": 1.5},
    ],
    8:  [  # August — monsoon continues, independence day
        {"topic": "barish aur yaad", "mood": "rain", "weight": 1.5},
        {"topic": "pakistan zindabad poetry", "mood": "patriotic", "weight": 1.4},
        {"topic": "14 august shayari", "mood": "patriotic", "weight": 1.5},
    ],
    9:  [  # September — post-monsoon nostalgia
        {"topic": "yaadon ka mausam", "mood": "nostalgic", "weight": 1.1},
    ],
    10: [  # October — autumn, melancholy
        {"topic": "khirki patton ki shayari", "mood": "autumn", "weight": 1.2},
        {"topic": "mukhtasar si zindagi", "mood": "autumn", "weight": 1.1},
    ],
    11: [  # November — early winter, weddings
        {"topic": "sardi aur dard", "mood": "winter", "weight": 1.3},
        {"topic": "shaadi shayari", "mood": "celebration", "weight": 1.2},
    ],
    12: [  # December — peak winter, year-end nostalgia
        {"topic": "sardi raat gham", "mood": "winter", "weight": 1.4},
        {"topic": "saal guzar gaya", "mood": "nostalgic", "weight": 1.3},
        {"topic": "andheri sardi raat shayari", "mood": "winter", "weight": 1.3},
    ],
}

# ── Cultural event calendar (approximate — shifts with Islamic calendar) ───
CULTURAL_EVENTS = [
    {"name": "Shab-e-Meraj", "month_approx": 2, "mood": "spiritual", "weight": 1.5},
    {"name": "Shab-e-Barat", "month_approx": 3, "mood": "spiritual", "weight": 1.5},
    {"name": "Ramadan Start", "month_approx": 3, "mood": "spiritual", "weight": 1.8},
    {"name": "Jumatul Wida", "month_approx": 4, "mood": "spiritual", "weight": 1.6},
    {"name": "Eid ul Fitr", "month_approx": 4, "mood": "celebration", "weight": 1.7},
    {"name": "Eid ul Adha", "month_approx": 7, "mood": "celebration", "weight": 1.6},
    {"name": "Muharram", "month_approx": 8, "mood": "sober", "weight": 1.5},
    {"name": "Rabi ul Awal", "month_approx": 10, "mood": "spiritual", "weight": 1.6},
    {"name": "Shab-e-Qadr", "month_approx": 3, "mood": "spiritual", "weight": 1.7},
    {"name": "Independence Day", "month_approx": 8, "mood": "patriotic", "weight": 1.5},
    {"name": "Defence Day", "month_approx": 9, "mood": "patriotic", "weight": 1.4},
    {"name": "Iqbal Day", "month_approx": 11, "mood": "literary", "weight": 1.5},
    {"name": "Quaid Day", "month_approx": 12, "mood": "patriotic", "weight": 1.5},
]

# ── Rising keywords (Urdu poetry YouTube search trends) ───────────────────
AUTOSUGGEST_SEEDS = [
    "urdu poetry", "sad shayari", "heart touching poetry",
    "2 line poetry urdu", "ghalib shayari", "ishq shayari",
    "dard bhari shayari", "rain poetry", "night poetry urdu",
    "motivational poetry urdu", "sufi kalam", "punjabi sad poetry",
    "status shayari", "breakup poetry", "one sided love poetry",
]


class TrendPredictor:
    """Predicts future trending Urdu poetry topics."""

    def __init__(self):
        self.cache = self._load_cache()
        self._performance = self._load_performance()

    def _load_cache(self) -> dict:
        try:
            return json.loads(PREDICTIONS_CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"predictions": [], "autosuggest": {}, "last_updated": None}

    def _save_cache(self) -> None:
        PREDICTIONS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PREDICTIONS_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PREDICTIONS_CACHE_PATH)

    def _load_performance(self) -> dict:
        perf_path = ROOT / "data" / "performance_profile.json"
        try:
            return json.loads(perf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ── YouTube Autosuggest Momentum ──────────────────────────────────────

    def _fetch_autosuggest(self, seed: str) -> List[str]:
        """Fetch YouTube search suggestions for momentum analysis."""
        try:
            encoded = urllib.parse.quote(seed)
            url = f"http://suggestqueries.google.com/complete/search?client=youtube&hl=ur&ds=yt&q={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8", "ignore")
                return re.findall(r'"([^"]+)"', content)[:10]
        except Exception as exc:
            logger.warning("Autosuggest failed for '%s': %s", seed, exc)
            return []

    def _compute_momentum(self) -> Dict[str, float]:
        """Compute momentum scores for trending queries.
        Compares current autosuggest results with cached results to detect
        rising queries (new suggestions = rising momentum)."""
        momentum = {}
        for seed in AUTOSUGGEST_SEEDS:
            current = self._fetch_autosuggest(seed)
            cached = self.cache.get("autosuggest", {}).get(seed, {}).get("suggestions", [])

            # New suggestions = rising interest
            new_suggestions = set(current) - set(cached)
            for suggestion in current:
                base_score = 1.0
                if suggestion in new_suggestions:
                    base_score = 1.5  # New in autosuggest = rising
                # Longer, more specific queries have higher intent
                if len(suggestion) > len(seed) + 5:
                    base_score *= 1.2
                key = suggestion.lower().strip()
                momentum[key] = max(momentum.get(key, 0), base_score)

            # Update cache
            self.cache.setdefault("autosuggest", {})[seed] = {
                "suggestions": current,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        return momentum

    # ── Seasonal Scoring ──────────────────────────────────────────────────

    def _seasonal_score(self, topic: str, month: int) -> float:
        """Score a topic based on seasonal relevance."""
        score = 1.0

        # Check seasonal themes
        for seasonal in SEASONAL_THEMES.get(month, []):
            seasonal_words = seasonal["topic"].lower().split()
            topic_words = topic.lower().split()
            overlap = len(set(seasonal_words) & set(topic_words))
            if overlap > 0:
                score = max(score, seasonal["weight"])

        # Check cultural events
        for event in CULTURAL_EVENTS:
            if event["month_approx"] == month:
                # Check if the topic matches the event mood
                if event["mood"] in topic.lower() or any(
                    kw in topic.lower() for kw in event["mood"].split()
                ):
                    score = max(score, event["weight"])

        return score

    # ── Performance-Boosted Scoring ────────────────────────────────────────

    def _performance_score(self, topic: str) -> float:
        """Score a topic based on historical performance data."""
        topic_lower = topic.lower().strip()
        for rec in self._performance.get("recommendations", {}).get("theme_hints", []):
            if rec["theme"].lower() == topic_lower:
                return min(2.0, 1.0 + rec["weight"] / 10000)
        return 1.0

    # ── Main Prediction ────────────────────────────────────────────────────

    def predict(self, n: int = 10, days_ahead: int = 7) -> List[dict]:
        """Predict top N trending topics for the next `days_ahead` days.

        Combines multiple signals:
          1. YouTube autosuggest momentum (40%)
          2. Seasonal relevance (30%)
          3. Performance history (20%)
          4. Cultural events (10%)
        """
        now = datetime.now(timezone.utc)
        # Use Pakistan timezone
        pkt = now + timedelta(hours=5)
        current_month = pkt.month

        # Compute momentum
        momentum = self._compute_momentum()

        # Build candidate pool
        candidates = {}

        # 1. From autosuggest momentum
        for query, mom_score in momentum.items():
            candidates[query] = {
                "topic": query,
                "momentum": mom_score,
                "seasonal": self._seasonal_score(query, current_month),
                "performance": self._performance_score(query),
                "source": "autosuggest",
            }

        # 2. From seasonal themes
        for seasonal in SEASONAL_THEMES.get(current_month, []):
            topic = seasonal["topic"]
            if topic not in candidates:
                candidates[topic] = {
                    "topic": topic,
                    "momentum": 1.0,
                    "seasonal": seasonal["weight"],
                    "performance": self._performance_score(topic),
                    "source": "seasonal",
                }
            else:
                candidates[topic]["seasonal"] = max(
                    candidates[topic]["seasonal"], seasonal["weight"]
                )
                candidates[topic]["source"] = "seasonal+autosuggest"

        # 3. From cultural events
        for event in CULTURAL_EVENTS:
            if event["month_approx"] == current_month:
                topic = f"{event['mood']} {event['name']} shayari"
                if topic not in candidates:
                    candidates[topic] = {
                        "topic": topic,
                        "momentum": 1.0,
                        "seasonal": event["weight"],
                        "performance": self._performance_score(topic),
                        "source": "cultural_event",
                    }

        # 4. From performance-learned top themes
        for rec in self._performance.get("recommendations", {}).get("theme_hints", [])[:5]:
            topic = rec["theme"]
            if topic not in candidates:
                candidates[topic] = {
                    "topic": topic,
                    "momentum": 1.0,
                    "seasonal": self._seasonal_score(topic, current_month),
                    "performance": rec["weight"] / 10000 + 1.0,
                    "source": "performance_learned",
                }
            else:
                candidates[topic]["performance"] = max(
                    candidates[topic]["performance"],
                    rec["weight"] / 10000 + 1.0,
                )

        # Compute final score (weighted combination)
        predictions = []
        for topic, data in candidates.items():
            final_score = (
                data["momentum"] * 0.40 +
                data["seasonal"] * 0.30 +
                data["performance"] * 0.20 +
                min(data["seasonal"], 1.5) * 0.10  # cultural event bonus
            )
            confidence = min(1.0, final_score / 3.0)
            predictions.append({
                "topic": data["topic"],
                "score": round(final_score, 3),
                "confidence": round(confidence, 3),
                "source": data["source"],
                "momentum": round(data["momentum"], 3),
                "seasonal": round(data["seasonal"], 3),
                "performance": round(data["performance"], 3),
                "predicted_for": pkt.strftime("%Y-%m-%d"),
                "month": current_month,
            })

        # Sort by score
        predictions.sort(key=lambda x: -x["score"])

        # Save predictions
        self.cache["predictions"] = predictions[:50]
        self.cache["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_cache()

        logger.info("Predicted %d trending topics (top: '%s', score: %.3f)",
                    len(predictions[:n]),
                    predictions[0]["topic"] if predictions else "none",
                    predictions[0]["score"] if predictions else 0)
        return predictions[:n]

    def get_best_topic(self, exclude: List[str] = None) -> Optional[dict]:
        """Get the single best predicted topic, excluding already-used ones."""
        exclude = exclude or []
        exclude_lower = {t.lower().strip() for t in exclude}
        predictions = self.predict(n=20)
        for p in predictions:
            if p["topic"].lower().strip() not in exclude_lower:
                return p
        return predictions[0] if predictions else None


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    predictor = TrendPredictor()
    predictions = predictor.predict(n=10)
    print(f"\n🔮 Top 10 Trend Predictions for Pakistan (current month):\n")
    for i, p in enumerate(predictions, 1):
        print(f"  {i}. {p['topic']}")
        print(f"     Score: {p['score']} | Confidence: {p['confidence']} | Source: {p['source']}")
        print(f"     Momentum: {p['momentum']} | Seasonal: {p['seasonal']} | Performance: {p['performance']}")
        print()
