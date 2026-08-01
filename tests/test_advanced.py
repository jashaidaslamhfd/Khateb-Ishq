#!/usr/bin/env python3
"""Tests for the Advanced Khateb-Ishq modules.

Run: python -m pytest tests/test_advanced.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── Performance Learner Tests ──────────────────────────────────────────────

class TestPerformanceLearner:
    """Tests for the PerformanceLearner module."""

    def test_load_empty_profile(self, tmp_path):
        """Empty profile loads without error."""
        from performance_learner import PerformanceLearner
        with patch.object(PerformanceLearner, '__init__', lambda self: None):
            learner = PerformanceLearner()
            learner.profile = {"version": 2, "last_updated": None,
                               "channel_stats": {}, "top_themes": [],
                               "top_poets": [], "top_publish_slots": [],
                               "top_voices": [], "top_caption_styles": [],
                               "viral_patterns": [], "seasonal_peaks": [],
                               "recommendations": {}}
            assert learner.profile["version"] == 2

    def test_classify_viral(self):
        """Videos with high views/subs ratio are classified as viral."""
        from performance_learner import PerformanceLearner
        with patch.object(PerformanceLearner, '__init__', lambda self: None):
            learner = PerformanceLearner()
            assert learner._classify_video(views=50000, subs=1000) == "viral"
            assert learner._classify_video(views=5000, subs=1000) == "average"
            assert learner._classify_video(views=500, subs=1000) == "underperformer"

    def test_classify_no_subs(self):
        """Classification works when subs=0."""
        from performance_learner import PerformanceLearner
        with patch.object(PerformanceLearner, '__init__', lambda self: None):
            learner = PerformanceLearner()
            assert learner._classify_video(views=500, subs=0) == "average"
            assert learner._classify_video(views=0, subs=0) == "underperformer"

    def test_recommend_themes(self):
        """recommend_themes returns top N themes."""
        from performance_learner import PerformanceLearner
        with patch.object(PerformanceLearner, '__init__', lambda self: None):
            learner = PerformanceLearner()
            learner.profile = {
                "recommendations": {
                    "theme_hints": [
                        {"theme": "ishq", "weight": 5000},
                        {"theme": "tanhai", "weight": 3000},
                        {"theme": "barish", "weight": 1000},
                    ]
                }
            }
            recs = learner.recommend_themes(2)
            assert len(recs) == 2
            assert recs[0]["theme"] == "ishq"

    def test_should_boost_theme(self):
        """should_boost_theme returns correct boost factor."""
        from performance_learner import PerformanceLearner
        with patch.object(PerformanceLearner, '__init__', lambda self: None):
            learner = PerformanceLearner()
            learner.profile = {
                "recommendations": {
                    "theme_hints": [
                        {"theme": "ishq", "weight": 20000},
                    ]
                }
            }
            boost = learner.should_boost_theme("ishq")
            assert boost >= 1.0  # Known theme should get boost
            boost_unknown = learner.should_boost_theme("unknown")
            assert boost_unknown == 1.0  # Unknown theme = neutral


# ── Hashtag Optimizer Tests ────────────────────────────────────────────────

class TestHashtagOptimizer:
    """Tests for the HashtagOptimizer module."""

    def test_optimize_basic(self):
        """Basic optimization returns valid tags."""
        from hashtag_optimizer import HashtagOptimizer
        with patch.object(HashtagOptimizer, '__init__', lambda self: None):
            opt = HashtagOptimizer()
            opt.cache = {"trends": {}}
            opt._performance = {}
            opt._extract_trending_tags = MagicMock(return_value=["trending1", "trending2"])
            opt._performance_weighted_tags = MagicMock(return_value={})

            tags = opt.optimize(script_data={
                "title": "غمِ دل",
                "poet": "Ghalib",
                "topic": "ishq juda'i",
                "source": "classic",
            })
            assert isinstance(tags, list)
            assert len(tags) > 0
            assert "khatebeishq" in tags  # Channel branding always present
            assert all(isinstance(t, str) for t in tags)

    def test_optimize_respects_max_tags(self):
        """Optimization respects MAX_TAGS limit."""
        from hashtag_optimizer import HashtagOptimizer
        with patch.object(HashtagOptimizer, '__init__', lambda self: None):
            opt = HashtagOptimizer()
            opt.cache = {"trends": {}}
            opt._performance = {}
            opt._extract_trending_tags = MagicMock(return_value=[])
            opt._performance_weighted_tags = MagicMock(return_value={})

            tags = opt.optimize(script_data={"title": "test", "topic": "test"})
            assert len(tags) <= 15  # Default MAX_TAGS

    def test_no_duplicate_tags(self):
        """No duplicate tags in output."""
        from hashtag_optimizer import HashtagOptimizer
        with patch.object(HashtagOptimizer, '__init__', lambda self: None):
            opt = HashtagOptimizer()
            opt.cache = {"trends": {}}
            opt._performance = {}
            opt._extract_trending_tags = MagicMock(return_value=[])
            opt._performance_weighted_tags = MagicMock(return_value={})

            tags = opt.optimize(script_data={"title": "urdupoetry", "topic": "urdupoetry"})
            assert len(tags) == len(set(tags))  # No duplicates

    def test_mood_specific_tags(self):
        """Rain-mood topics get rain-specific tags."""
        from hashtag_optimizer import HashtagOptimizer
        with patch.object(HashtagOptimizer, '__init__', lambda self: None):
            opt = HashtagOptimizer()
            opt.cache = {"trends": {}}
            opt._performance = {}
            opt._extract_trending_tags = MagicMock(return_value=[])
            opt._performance_weighted_tags = MagicMock(return_value={})

            tags = opt.optimize(script_data={"title": "barish", "topic": "barish shayari"})
            # Should include rain-related tags
            assert any("barish" in t or "rain" in t for t in tags)


# ── Trend Predictor Tests ──────────────────────────────────────────────────

class TestTrendPredictor:
    """Tests for the TrendPredictor module."""

    def test_seasonal_score(self):
        """Seasonal scoring works for known months."""
        from trend_predictor import TrendPredictor
        with patch.object(TrendPredictor, '__init__', lambda self: None):
            predictor = TrendPredictor()
            # July = monsoon → barish should score high
            july_score = predictor._seasonal_score("barish shayari", 7)
            assert july_score > 1.0  # Barish in July should be boosted

    def test_seasonal_score_off_season(self):
        """Off-season topics get neutral score."""
        from trend_predictor import TrendPredictor
        with patch.object(TrendPredictor, '__init__', lambda self: None):
            predictor = TrendPredictor()
            # "barish" in January (winter) should be neutral
            jan_score = predictor._seasonal_score("barish shayari", 1)
            assert jan_score == 1.0  # No seasonal boost

    def test_predict_returns_list(self):
        """predict() returns a list of predictions."""
        from trend_predictor import TrendPredictor
        with patch.object(TrendPredictor, '__init__', lambda self: None):
            predictor = TrendPredictor()
            predictor.cache = {"autosuggest": {}}
            predictor._performance = {}
            predictor._fetch_autosuggest = MagicMock(return_value=[])
            predictor._compute_momentum = MagicMock(return_value={})
            predictor._seasonal_score = MagicMock(return_value=1.0)
            predictor._performance_score = MagicMock(return_value=1.0)
            predictor._save_cache = MagicMock()

            predictions = predictor.predict(n=5)
            assert isinstance(predictions, list)


# ── Smart Theme Selector Tests ─────────────────────────────────────────────

class TestSmartThemeSelector:
    """Tests for the SmartThemeSelector module."""

    def test_select_returns_dict(self):
        """select() returns a valid theme dict."""
        from smart_theme_selector import SmartThemeSelector
        with patch.object(SmartThemeSelector, '__init__', lambda self: None):
            selector = SmartThemeSelector()
            selector.performance = {}
            selector.catalog = [{"theme": "test theme", "series_title": "Kalam #1"}]
            selector.used_themes = set()
            selector._refresh_used_themes = MagicMock()

            result = selector.select(strategy="catalog_random")
            assert isinstance(result, dict)
            assert "topic" in result
            assert "strategy" in result

    def test_get_theme_compatible(self):
        """get_theme() is backwards-compatible with theme_fetcher."""
        from smart_theme_selector import get_theme
        with patch('smart_theme_selector.SmartThemeSelector') as MockSelector:
            instance = MockSelector.return_value
            instance.select.return_value = {
                "topic": "test",
                "series_title": "Kalam #1: Test",
                "source": "test",
            }
            result = get_theme()
            assert "topic" in result
            assert "series_title" in result


# ── Multi-Platform Poster Tests ────────────────────────────────────────────

class TestMultiPlatformPoster:
    """Tests for the MultiPlatformPoster module."""

    def test_no_platforms_configured(self):
        """Returns YouTube-only mode when no platforms configured."""
        from multi_platform import MultiPlatformPoster
        with patch.object(MultiPlatformPoster, '__init__', lambda self: None):
            poster = MultiPlatformPoster()
            poster.enabled_platforms = []
            poster.state = {"platforms": {}}
            poster._save_state = MagicMock()

            result = poster.post_all("video.mp4", {"title": "test"})
            assert result["success"] is True
            assert "YouTube-only" in result["message"]

    def test_build_tiktok_description(self):
        """TikTok description is within limits."""
        from multi_platform import MultiPlatformPoster
        with patch.object(MultiPlatformPoster, '__init__', lambda self: None):
            poster = MultiPlatformPoster()
            desc = poster._build_tiktok_description({
                "title": "غمِ دل",
                "poet": "Ghalib",
                "tags": ["urdupoetry", "shayari"],
            })
            assert len(desc) <= 150
            assert "urdupoetry" in desc

    def test_build_instagram_description(self):
        """Instagram description includes hashtags."""
        from multi_platform import MultiPlatformPoster
        with patch.object(MultiPlatformPoster, '__init__', lambda self: None):
            poster = MultiPlatformPoster()
            desc = poster._build_instagram_description({
                "title": "غمِ دل",
                "poet": "Ghalib",
                "tags": ["urdupoetry"],
            })
            assert "#" in desc
            assert "urdupoetry" in desc


# ── Engagement Bot Tests ──────────────────────────────────────────────────

class TestEngagementBot:
    """Tests for the EngagementBot module."""

    def test_positive_detection(self):
        """Positive comments are detected correctly."""
        from engagement_bot import EngagementBot
        with patch.object(EngagementBot, '__init__', lambda self: None):
            bot = EngagementBot()
            assert bot._is_positive_comment("بہت اچھی شاعری ہے") is True
            assert bot._is_positive_comment("mashallah zabardast") is True
            assert bot._is_positive_comment("❤️❤️") is True

    def test_negative_not_detected(self):
        """Non-positive comments are not flagged."""
        from engagement_bot import EngagementBot
        with patch.object(EngagementBot, '__init__', lambda self: None):
            bot = EngagementBot()
            assert bot._is_positive_comment("asdfgh random") is False

    def test_should_not_reply_to_own(self):
        """Don't reply to own comments."""
        from engagement_bot import EngagementBot
        with patch.object(EngagementBot, '__init__', lambda self: None):
            bot = EngagementBot()
            assert bot._should_reply("nice", "Khateb-e-Ishq") is False

    def test_generate_engagement_post(self):
        """Engagement post is generated in Urdu."""
        from engagement_bot import EngagementBot
        with patch.object(EngagementBot, '__init__', lambda self: None):
            bot = EngagementBot()
            post = bot.generate_engagement_post({"title": "غمِ دل", "poet": "Ghalib"})
            assert isinstance(post, str)
            assert len(post) > 0

    def test_generate_poll_post(self):
        """Poll post has question and options."""
        from engagement_bot import EngagementBot
        with patch.object(EngagementBot, '__init__', lambda self: None):
            bot = EngagementBot()
            poll = bot.generate_poll_post()
            assert "question" in poll
            assert "options" in poll
            assert len(poll["options"]) >= 2


# ── Integration Tests ──────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for the advanced pipeline."""

    def test_smart_theme_fallback_chain(self):
        """Smart theme selector falls back through strategies."""
        from smart_theme_selector import SmartThemeSelector
        with patch.object(SmartThemeSelector, '__init__', lambda self: None):
            selector = SmartThemeSelector()
            selector.performance = {}
            selector.catalog = []
            selector.used_themes = set()
            selector._refresh_used_themes = MagicMock()

            # All strategies fail → ultimate fallback
            result = selector.select()
            assert result["topic"]  # Always returns something

    def test_hashtag_optimizer_with_script(self):
        """Hashtag optimizer works with a realistic script."""
        from hashtag_optimizer import HashtagOptimizer
        with patch.object(HashtagOptimizer, '__init__', lambda self: None):
            opt = HashtagOptimizer()
            opt.cache = {"trends": {}}
            opt._performance = {}
            opt._extract_trending_tags = MagicMock(return_value=[])
            opt._performance_weighted_tags = MagicMock(return_value={})

            tags = opt.optimize(script_data={
                "title": "غمِ محبت",
                "poet": "Mirza Ghalib",
                "topic": "ishq aur juda'i",
                "source": "classic",
                "tags": ["urdupoetry", "shayari"],
            })
            assert len(tags) > 5
            assert "khatebeishq" in tags


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
