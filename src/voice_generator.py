#!/usr/bin/env python3
"""Urdu voice generation via Edge-TTS (Microsoft neural voices).

Why Edge-TTS first: Chatterbox/Kokoro-family models in this stack are
English-language — feeding them Urdu produced broken talaffuz, which is
fatal for poetry. Microsoft's ur-PK voices are native-Urdu neural models:

  ur-PK-AsadNeural  (male, deep — ideal for sad/gham poetry)
  ur-PK-UzmaNeural  (female, soft)
  ur-IN-SalmanNeural / ur-IN-GulNeural (Indian-Urdu alternates)

Pacing: poetry needs breath. rate="-12%" default slows delivery without
robotics; Urdu punctuation (۔, ،) drives edge's natural pauses.
"""

import asyncio
import logging
import os
import tempfile
from typing import Dict, List

import numpy as np
import soundfile as sf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Voice pool — rotate or pin via URDU_VOICE env. "asad" is the channel voice.
_VOICE_POOL = {
    "asad": "ur-PK-AsadNeural",
    "uzma": "ur-PK-UzmaNeural",
    "salman": "ur-IN-SalmanNeural",
    "gul": "ur-IN-GulNeural",
}


def _resolve_voices() -> List[str]:
    raw = os.environ.get("URDU_VOICE", "asad").strip().lower()
    if raw == "rotate":
        return [ _VOICE_POOL["asad"], _VOICE_POOL["uzma"] ]
    return [_VOICE_POOL.get(raw, _VOICE_POOL["asad"])]


def _rate() -> str:
    # negative = slower. clamp -25%..+5% (sad poetry lives around -8..-15)
    try:
        value = float(os.environ.get("URDU_TTS_RATE", "-12"))
    except ValueError:
        value = -12.0
    value = max(-25.0, min(5.0, value))
    return f"{value:+.0f}%"


def _engine() -> str:
    """Voice engine: 'edge' (free, native-Urdu neural — default) or 'elevenlabs'
    (user's OWN cloned voice). Falls back to edge with a loud warning if the
    clone credentials are not configured, so the channel can never break."""
    eng = os.environ.get("VOICE_ENGINE", "edge").strip().lower()
    if eng == "elevenlabs":
        if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
            return "elevenlabs"
        logger.warning("VOICE_ENGINE=elevenlabs but ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID "
                       "missing — falling back to Edge-TTS for this run")
        return "edge"
    return "edge"


async def _synth(text: str, voice: str, rate: str, out_path: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(out_path)


def _synth_elevenlabs(text: str, out_path: str) -> None:
    """User's cloned voice via ElevenLabs multilingual model.

    eleven_multilingual_v2 supports Urdu; the voice itself is an Instant Voice
    Clone of the channel owner (see README → Cloned voice). Cost: per character,
    so keep poetry short (it already is)."""
    import requests
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                 "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.85, "style": 0.25},
        },
        timeout=120,
    )
    if resp.status_code != 200 or len(resp.content) < 1000:
        raise RuntimeError(f"ElevenLabs TTS failed: {resp.status_code} {resp.text[:150]}")
    with open(out_path, "wb") as fh:
        fh.write(resp.content)


def generate_voice_segments(scenes: List[dict], output_dir: str = "output/segments", **_ignored) -> List[Dict]:
    """One WAV segment per scene caption. All segments must use ONE voice —
    a poem that switches speaker mid-sher sounds like a bad radio edit."""
    os.makedirs(output_dir, exist_ok=True)
    engine = _engine()
    voices = _resolve_voices()
    voice = voices[0]  # deterministic default; one speaker per poem, always
    rate = _rate()
    speaker_tag = os.environ.get("ELEVENLABS_VOICE_ID", "")[:8] if engine == "elevenlabs" else voice
    segments = []
    for i, scene in enumerate(scenes):
        caption = (scene.get("caption", "") if isinstance(scene, dict) else str(scene)).strip() or "۔"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            if engine == "elevenlabs":
                _synth_elevenlabs(caption, tmp_path)
            else:
                asyncio.run(_synth(caption, voice, rate, tmp_path))
            audio, sr = sf.read(tmp_path, dtype="float32")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.size == 0:
            raise RuntimeError(f"Edge-TTS returned empty audio for scene {i+1}: {caption[:40]}")
        peak = float(np.abs(audio).max())
        if peak > 1.0:
            audio = audio / peak * 0.95
        path = os.path.join(output_dir, f"seg_{i}.wav")
        sf.write(path, audio, sr)
        segments.append({"path": path, "duration": len(audio) / sr,
                         "caption": caption, "tts_engine": f"{engine}:{speaker_tag}"})
        logger.info("Segment %d/%d via %s (%.1fs)", i + 1, len(scenes), speaker_tag, len(audio) / sr)
    engines = {s["tts_engine"] for s in segments}
    if len(engines) != 1:
        raise RuntimeError(f"Mixed voices in one video: {engines}")
    logger.info("Total narration: %.1fs via %s @ %s",
                sum(s["duration"] for s in segments), voice, rate)
    return segments
