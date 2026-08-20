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
    # negative = slower. -14% is the golden mushaira sad poetry pace
    try:
        value = float(os.environ.get("URDU_TTS_RATE", "-14"))
    except ValueError:
        value = -14.0
    value = max(-25.0, min(5.0, value))
    return f"{value:+.0f}%"


def _engine() -> str:
    """Voice engine: 'edge' (free, native-Urdu neural — default), 'elevenlabs'
    (paid cloud clone) or 'qwenclone' (owner's OWN voice, free, zero-shot
    Qwen3-TTS — see src/voice_clone.py). Any misconfiguration loudly falls
    back to edge so the channel can never break."""
    eng = os.environ.get("VOICE_ENGINE", "edge").strip().lower()
    if eng in ("qwenclone", "qwen3", "clone"):
        try:
            import voice_clone
            if voice_clone.reference_ready():
                return "qwenclone"
            logger.warning("VOICE_ENGINE=qwenclone but no reference WAV found — falling back to Edge-TTS")
        except Exception as exc:
            logger.warning("qwenclone unavailable (%s) — falling back to Edge-TTS", exc)
        return "edge"
    if eng == "elevenlabs":
        if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
            return "elevenlabs"
        logger.warning("VOICE_ENGINE=elevenlabs but ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID "
                       "missing — falling back to Edge-TTS for this run")
        return "edge"
    return "edge"


class CloneHung(RuntimeError):
    """Raised when a single voice-clone segment exceeds CLONE_SEGMENT_TIMEOUT
    and the hard alarm fires. The outer poem loop catches it and re-renders
    the whole poem via edge-TTS so one stuck clone never parks a run.
    (2026-08-20: promoted to module scope — it was defined inside
    _synth_clone_guarded but referenced at module level, which raised a
    NameError on the very first edge-TTS run and killed the pipeline.)"""


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


def _master_vocal_audio(in_wav: str, out_wav: str) -> None:
    """Master the raw TTS voice to give it deep studio baritone warmth,
    crystal clarity, and broadcast loudness (-14 LUFS)."""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", in_wav,
        "-af", (
            "highpass=f=80,"                           # Clean low-end rumble
            "equalizer=f=220:t=q:w=1.2:g=2.2,"          # Warm baritone chest resonance
            "equalizer=f=3600:t=q:w=1.8:g=1.2,"         # Crisp speech articulation
            "loudnorm=I=-14:TP=-1.5:LRA=8"              # Social media broadcast standard
        ),
        "-ar", "44100", "-ac", "2", out_wav
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as exc:
        logger.warning("Vocal mastering filter fallback (using raw audio): %s", exc)
        if in_wav != out_wav and os.path.exists(in_wav):
            import shutil
            shutil.copy(in_wav, out_wav)


def _synth_clone_guarded(text: str, out_path: str) -> None:
    """Clone one segment with a hard hang-guard.

    2026-07-25 live proof: segment 3 of a healthy script froze the CPU clone
    for ~56 minutes and the whole upload died (run was cancelled by hand).
    No segment may ever again park a pipeline run: CLONE_SEGMENT_TIMEOUT
    (default 240s ≈ 4× a healthy 40-60s segment) aborts it loudly.
    """
    import signal

    timeout = int(os.environ.get("CLONE_SEGMENT_TIMEOUT", "240"))

    def _boom(*_a):
        raise CloneHung(f"voice-clone segment exceeded {timeout}s")

    signal.signal(signal.SIGALRM, _boom)
    signal.alarm(timeout)
    try:
        import voice_clone
        voice_clone.synth_clone(text, out_path)
    finally:
        signal.alarm(0)


def generate_voice_segments(scenes: List[dict], output_dir: str = "output/segments", **_ignored) -> List[Dict]:
    """One WAV segment per scene caption. All segments must use ONE voice —
    a poem that switches speaker mid-sher sounds like a bad radio edit."""
    os.makedirs(output_dir, exist_ok=True)
    engine = _engine()
    voices = _resolve_voices()
    voice = voices[0]  # deterministic default; one speaker per poem, always
    rate = _rate()

    def render(eng: str) -> List[Dict]:
        speaker_tag = (os.environ.get("ELEVENLABS_VOICE_ID", "")[:8] if eng == "elevenlabs"
                       else "owner-clone" if eng == "qwenclone" else voice)
        segments = []
        for i, scene in enumerate(scenes):
            caption = (scene.get("caption", "") if isinstance(scene, dict) else str(scene)).strip() or "۔"
            suffix = ".wav" if eng == "qwenclone" else ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
            try:
                if eng == "elevenlabs":
                    _synth_elevenlabs(caption, tmp_path)
                elif eng == "qwenclone":
                    _synth_clone_guarded(caption, tmp_path)
                else:
                    asyncio.run(_synth(caption, voice, rate, tmp_path))
                audio, sr = sf.read(tmp_path, dtype="float32")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if audio.size == 0:
                raise RuntimeError(f"TTS returned empty audio for scene {i+1}: {caption[:40]}")
            peak = float(np.abs(audio).max())
            if peak > 1.0:
                audio = audio / peak * 0.95
            raw_path = os.path.join(output_dir, f"raw_seg_{i}.wav")
            sf.write(raw_path, audio, sr)
            _master_vocal_audio(raw_path, tmp_path + ".master.wav")
            if os.path.exists(raw_path):
                os.remove(raw_path)
            dur_audio, dur_sr = sf.read(tmp_path + ".master.wav")
            duration_s = len(dur_audio) / dur_sr
            segments.append({"path": tmp_path + ".master.wav", "duration": duration_s,
                             "caption": caption, "tts_engine": f"{eng}:{speaker_tag}"})
            logger.info("Segment %d/%d via %s (%.1fs) [Mastered]", i + 1, len(scenes), speaker_tag, duration_s)
        engines = {s["tts_engine"] for s in segments}
        if len(engines) != 1:
            raise RuntimeError(f"Mixed voices in one video: {engines}")
        logger.info("Total narration: %.1fs via %s @ %s",
                    sum(s["duration"] for s in segments), voice, rate)
        return segments

    try:
        return render(engine)
    except CloneHung as e:
        # One stuck segment froze a live run before — never again. Restart the
        # WHOLE poem on edge so the single-voice rule survives and the upload
        # still happens today instead of dying with a cancelled workflow.
        logger.warning("%s — clone hung; regenerating entire poem via edge TTS", e)
        if engine != "qwenclone":
            raise
        return render("edge")
