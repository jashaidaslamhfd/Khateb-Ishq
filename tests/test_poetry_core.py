"""Offline tests for the Khateb-Ishq poetry pipeline — no API calls."""

import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ThemeBankTests(unittest.TestCase):
    def test_500_unique_themes(self):
        themes = json.loads((ROOT / "data" / "poetry_themes.json").read_text(encoding="utf-8"))
        self.assertEqual(len(themes), 500)
        keys = [t["theme"] for t in themes]
        self.assertEqual(len(set(keys)), 500, "themes must be unique")

    def test_series_numbers_sequential(self):
        themes = json.loads((ROOT / "data" / "poetry_themes.json").read_text(encoding="utf-8"))
        self.assertEqual([t["series_number"] for t in themes][:5], [1, 2, 3, 4, 5])


class PoetryValidationTests(unittest.TestCase):
    def setUp(self):
        try:
            import importlib
            self.sg = importlib.import_module("script_generator")
        except ModuleNotFoundError as exc:
            self.skipTest(f"deps missing: {exc}")

    def _valid_fixture(self):
        return {
            "title": "تنہائی کی رات",
            "hook": "رات اور تنہائی کا سازش ہوتی ہے",
            "cta": "مزید شاعری کے لیے فالو کیجیے",
            "description": "An Urdu nazm on 2am loneliness.",
            "scenes": [
                {"visual": "rainy window, dim lamp, moody night", "caption": "رات اور تنہائی کا سازش ہوتی ہے"},
                {"visual": "old diary on wooden table", "caption": "ہو کے نہ بند یہ دروازہ دل کا کسی بھی صورت حال میں اکیلے رہ گئے"},
                {"visual": "empty chair, cold tea", "caption": "جنہیں اداسی ہو گئی ہم ان دعاؤں میں یاد رکھا کریں گے خاموشی سے"},
                {"visual": "dawn light through curtains", "caption": "رات اور تنہائی پھر اک دوسرے سے ملیں گی فردا کی رات میں"},
            ],
        }

    def test_valid_urdu_script_passes(self):
        valid, issues = self.sg._validate_script(self._valid_fixture())
        self.assertTrue(valid, issues)

    def test_english_caption_is_rejected(self):
        data = self._valid_fixture()
        data["scenes"][1]["caption"] = "This is an English caption that slipped through."
        valid, issues = self.sg._validate_script(data)
        self.assertFalse(valid)
        self.assertTrue(any("not Urdu" in issue for issue in issues))

    def test_too_few_scenes_rejected(self):
        data = self._valid_fixture()
        data["scenes"] = data["scenes"][:2]
        valid, issues = self.sg._validate_script(data)
        self.assertFalse(valid)


class PublishSlotsTests(unittest.TestCase):
    def setUp(self):
        try:
            import importlib
            self.scheduler = importlib.import_module("scheduler")
        except ModuleNotFoundError as exc:
            self.skipTest(f"deps missing: {exc}")

    def test_publish_at_hits_a_pkt_slot_in_future(self):
        import pytz
        publish_at = self.scheduler.compute_publish_at()
        parsed = datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
        self.assertGreaterEqual(parsed, datetime.now(pytz.UTC) + timedelta(minutes=25))
        slot_pkt = parsed.astimezone(pytz.timezone("Asia/Karachi"))
        self.assertIn((slot_pkt.hour, slot_pkt.minute), [(10, 0), (14, 0), (21, 0)])

    def test_slots_are_env_overridable(self):
        import os
        old = os.environ.get("PUBLISH_SLOTS")
        try:
            os.environ["PUBLISH_SLOTS"] = "08:00,20:00"
            import pytz
            parsed = datetime.strptime(self.scheduler.compute_publish_at(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
            slot_pkt = parsed.astimezone(pytz.timezone("Asia/Karachi"))
            self.assertIn((slot_pkt.hour, slot_pkt.minute), [(8, 0), (20, 0)])
        finally:
            if old is None:
                os.environ.pop("PUBLISH_SLOTS", None)
            else:
                os.environ["PUBLISH_SLOTS"] = old


class PublicApiTests(unittest.TestCase):
    def test_lazy_exports_resolve_names(self):
        import src
        for name in src.__all__:
            self.assertIn(name, src._LAZY_EXPORTS)
        with self.assertRaises(AttributeError):
            src.NOT_REAL_123


class GitignoreSafetyTests(unittest.TestCase):
    def test_secrets_patterns_present(self):
        text = (ROOT / ".gitignore").read_text()
        for pattern in ("oauth_backup.json", "client_secrets*.json", "token*.json"):
            self.assertIn(pattern, text)


if __name__ == "__main__":
    unittest.main()
