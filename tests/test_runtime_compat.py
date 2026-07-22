"""Runtime-compat regression tests — lock the three fixes from the first
CI run (2026-07-22, workflow #1):

1. Pillow >= 10 removed Image.ANTIALIAS, but moviepy 1.x's resize fx still
   references it -> video_editor must install a LANCZOS shim at import time.
2. The image_provider registry contract is generate(prompt, seed, scene_text)
   -> (bytes, ext); image_generator must call it exactly like that and must
   try the next provider when one fails.
3. The spoken-word floor must match reality: voiceover = scene captions ONLY
   (hook/cta are metadata), so a 2-couplet script is ~34-48 words.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

URDU_SHER_A = "دل کے ساگر میں لہر اٹھی پھر چپ ہو گئی"      # 10 words
URDU_SHER_B = "شام ڈھلی یادوں کا قافلہ گھر تک نہ آیا"       # 9 words


class PillowCompatTests(unittest.TestCase):
    def test_antialias_constant_available(self):
        try:
            import video_editor  # noqa: F401  (import applies the shim)
            from PIL import Image
        except Exception as exc:  # heavy deps (numpy/soundfile) missing locally
            self.skipTest(f"video_editor deps unavailable here: {exc}")
        self.assertTrue(
            hasattr(Image, "ANTIALIAS"),
            "Pillow>=10 removed ANTIALIAS — video_editor must shim it for moviepy 1.x",
        )


class ImageProviderContractTests(unittest.TestCase):
    def setUp(self):
        try:
            import image_generator
        except Exception as exc:
            self.skipTest(f"image_generator import failed: {exc}")
        self.ig = image_generator
        self._orig = self.ig.available_providers

    def tearDown(self):
        self.ig.available_providers = self._orig

    def _run_in_tmp(self, index, scene):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                out = self.ig.generate_scene_image(index, scene, set(), set())
                out["_existed_in_tmp"] = os.path.exists(out["path"])  # path is relative!
                return out
            finally:
                os.chdir(old)

    def test_provider_called_with_seed_and_scene_text(self):
        calls = []

        def fake_provider(prompt, seed, scene_text=None):
            calls.append((prompt, seed, scene_text))
            return (b"\x89PNG" + b"x" * 9000, "png")

        self.ig.available_providers = lambda: [{"name": "FakeProvider", "generate": fake_provider}]
        out = self._run_in_tmp(0, {"visual": "rain on window", "caption": URDU_SHER_A})

        self.assertEqual(out["source"], "FakeProvider")
        self.assertTrue(out["_existed_in_tmp"], "image bytes must be written to disk")
        self.assertEqual(out["path"].endswith(".png"), True)
        self.assertEqual(len(calls), 1, "first successful provider should be enough")
        prompt, seed, scene_text = calls[0]
        self.assertIsInstance(seed, int, "providers require a positional seed argument")
        self.assertEqual(scene_text, URDU_SHER_A)
        self.assertIn("rain on window", prompt)

    def test_second_provider_used_when_first_fails(self):
        def bad(prompt, seed, scene_text=None):
            raise RuntimeError("boom")

        def good(prompt, seed, scene_text=None):
            return (b"jfif" + b"y" * 9000, "jpg")

        self.ig.available_providers = lambda: [{"name": "Bad", "generate": bad},
                                               {"name": "Good", "generate": good}]
        out = self._run_in_tmp(1, {"visual": "empty chair", "caption": URDU_SHER_B})
        self.assertEqual(out["source"], "Good", "must fall through to the next provider")

    def test_too_small_payload_is_rejected(self):
        def tiny(prompt, seed, scene_text=None):
            return (b"err", "jpg")  # < MIN_BYTES

        self.ig.available_providers = lambda: [{"name": "Tiny", "generate": tiny}]
        try:
            out = self._run_in_tmp(2, {"visual": "x", "caption": URDU_SHER_A})
            self.assertEqual(out["source"], "placeholder",
                             "tiny payloads must not be saved as images (placeholder fallback)")
        except RuntimeError:
            pass  # no assets/placeholder.png on this machine — also acceptable


class SpokenFloorTests(unittest.TestCase):
    def setUp(self):
        try:
            import script_generator
        except Exception as exc:
            self.skipTest(f"script_generator unavailable: {exc}")
        self.sg = script_generator

    def _script(self, captions):
        return {
            "title": "درد کی رات",
            "hook": "کچھ کہنے کی رات ہے",
            "cta": "فالو ضرور کریں",
            "scenes": [{"visual": "moody rain window", "caption": c} for c in captions],
        }

    def test_two_couplets_pass_new_floor(self):
        # 48 spoken words across 3 scenes — the 2-sher shape CI kept rejecting at 45-min
        captions = [URDU_SHER_A + " " + URDU_SHER_B, URDU_SHER_B + " " + URDU_SHER_A, URDU_SHER_A]
        ok, issues = self.sg._validate_script(self._script(captions))
        spoken_issues = [i for i in issues if "Spoken words" in i]
        self.assertFalse(spoken_issues, f"2-couplet script rejected by floor: {issues}")

    def test_tiny_script_still_rejected(self):
        ok, issues = self.sg._validate_script(self._script(["ایک دو تین", "چار پانچ", "چھ سات دن"]))
        self.assertFalse(ok)
        self.assertTrue(any("Spoken words" in i for i in issues))

    def test_roman_caption_still_rejected(self):
        captions = ["dard ki raat bahut lambi hai", "shama jal ke khamosh ho gayi", "dil mein ek dard hai"]
        ok, issues = self.sg._validate_script(self._script(captions))
        self.assertFalse(ok)
        self.assertTrue(any("not Urdu script" in i for i in issues))

    def test_mixed_latin_word_in_urdu_caption_rejected(self):
        # THE bug from run #2: one Urdu word made _has_urdu pass, then TTS spoke
        # the Latin word in an English accent. Must be caught now.
        captions = [URDU_SHER_A + " raat hoti hai tonight", URDU_SHER_B, URDU_SHER_A + " " + URDU_SHER_B]
        ok, issues = self.sg._validate_script(self._script(captions))
        self.assertFalse(ok, "Latin word inside an Urdu caption must fail validation")
        self.assertTrue(any("Latin" in i for i in issues))

    def test_latin_title_rejected(self):
        s = self._script([URDU_SHER_A, URDU_SHER_B, URDU_SHER_A + " " + URDU_SHER_B])
        s["title"] = "sad raat کی ویڈیو"
        ok, issues = self.sg._validate_script(s)
        self.assertFalse(ok)
        self.assertTrue(any("title" in i and "Latin" in i for i in issues))

    def test_digits_and_urdu_punctuation_allowed(self):
        captions = ["رات کے 2 بجے کی سکرین", URDU_SHER_A + " " + URDU_SHER_B, URDU_SHER_A + "۔"]
        ok, issues = self.sg._validate_script(self._script(captions))
        self.assertEqual([i for i in issues if "Latin" in i], [],
                         f"digits/punct must not trigger the Latin filter: {issues}")


class VoiceEngineTests(unittest.TestCase):
    def setUp(self):
        try:
            import voice_generator
        except Exception as exc:
            self.skipTest(f"voice_generator unavailable: {exc}")
        self.vg = voice_generator

    def test_default_engine_is_edge(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VOICE_ENGINE", None)
            self.assertEqual(self.vg._engine(), "edge")

    def test_clone_request_without_creds_falls_back(self):
        from unittest.mock import patch
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID")}
        with patch.dict(os.environ, clean, clear=True):
            os.environ["VOICE_ENGINE"] = "elevenlabs"
            self.assertEqual(self.vg._engine(), "edge",
                             "missing clone creds must NEVER break the run")

    def test_clone_engine_active_with_creds(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"VOICE_ENGINE": "elevenlabs",
                                     "ELEVENLABS_API_KEY": "x",
                                     "ELEVENLABS_VOICE_ID": "y"}, clear=False):
            self.assertEqual(self.vg._engine(), "elevenlabs")


if __name__ == "__main__":
    unittest.main()
