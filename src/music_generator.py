"""Per-video UNIQUE sad-poetry BGM — the music you hear behind viral
TikTok/YouTube sad-poetry shorts (emotional piano + crying violin + rain).

2026-08-19 upgrade (owner: "free engine, no API key needed"):
  * PRIMARY ENGINE (free): a procedural composer in this file generates a
    brand-new track for EVERY video — randomized minor-key progression,
    randomized piano melody with human timing jitter, violin counter-line,
    rain ambience, soft reverb. No two videos ever share a track, and
    nothing is re-used stock, so there is zero Content-ID risk.
  * PREMIUM UPGRADE (optional): if MODELSLAB_API_KEY is set in secrets, a
    real AI text-to-music track is fetched first — paid quality, still
    per-video unique.
  * LAST RESORT: legacy mood-picked stock track. The render NEVER blocks.

Everything renders to 44.1 kHz WAV with a proper loop-friendly fade, so
video_editor's loop fader can stretch the bed across any video length.
"""
import hashlib
import os
import random
import time
import wave
import urllib.parse
import urllib.request

import re

import numpy as np
import requests

BASE_VAULT = os.path.join("assets", "music", "generated")
MAX_POLL = 10
POLL_INTERVAL = 8
SR = 44100

# ---------------------------------------------------------------------------
# PREMIUM (optional): ModelsLab text-to-music — only when the key exists
# ---------------------------------------------------------------------------
_BASE_PROMPT = (
    "Melancholic cinematic sad instrumental, heartbreaking emotional piano "
    "melody with soft crying violin strings, gentle rain ambience in the "
    "background, slow {bpm} BPM, minor key, deep and painful, Pakistani sad "
    "poetry background music, TikTok viral sad aesthetic, instrumental only, "
    "no vocals, no drums, no percussion, smooth and seamless loop-friendly, "
    "studio quality"
)
_MUSIC_GEN_URL = "https://modelslab.com/api/v6/voice/music_gen"


def _make_prompt(theme: str, bpm: int = 65) -> str:
    clean = re.sub(r"[^\w\s\u0600-\u06FF]+", "", theme or "")
    words = " ".join(clean.split())[:60]
    text = _BASE_PROMPT.format(bpm=bpm)
    if words:
        text += f", inspired mood: {words}"
    return text


def generate_sad_music(theme: str = "", duration: int = 30) -> str | None:
    """Premium ModelsLab generation. Returns output path or None on failure
    (caller falls back to the free engine, never the stock vault)."""
    api_key = os.environ.get("MODELSLAB_API_KEY", "").strip()
    if not api_key:
        return None  # key not set -> free engine takes over
    import logging
    logger = logging.getLogger("music_generator")
    os.makedirs(BASE_VAULT, exist_ok=True)
    payload = {
        "key": api_key,
        "prompt": _make_prompt(theme),
        "duration": max(20, duration),
        "output_format": "wav",
    }
    try:
        resp = requests.post(_MUSIC_GEN_URL, json=payload, timeout=120)
    except Exception as exc:  # noqa: BLE001 - fallback is intentional
        logger.warning("Music API unreachable (%s) — free engine instead", exc)
        return None
    if resp.status_code == 429:
        logger.warning("Music API rate-limited — free engine instead")
        return None
    if resp.status_code != 200:
        logger.warning("Music API HTTP %s — free engine instead", resp.status_code)
        return None
    data = resp.json()
    status = data.get("status")
    urls = data.get("output") or []
    if status == "success" and urls:
        return _download_track(urls[0], theme)
    if status in ("processing", "not_found") and data.get("fetch_result"):
        fetch = data["fetch_result"]
        for _ in range(MAX_POLL):
            time.sleep(POLL_INTERVAL)
            try:
                with urllib.request.urlopen(fetch, timeout=30) as r:
                    d = json.load(r)
            except Exception:  # noqa: BLE001
                continue
            out = d.get("output") or []
            if d.get("status") == "success" and out:
                return _download_track(out[0], theme)
            if d.get("status") == "failed":
                return None
        logger.warning("Music API polling timeout — free engine instead")
    return None


def _download_track(url: str, theme: str) -> str:
    slug = re.sub(r"[^\w]+", "_", theme or "sad")[:40]
    path = os.path.join(BASE_VAULT,
                        f"viral_sad_{slug}_{int(time.time())}_{random.randint(100,999)}".strip() + ".wav")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    except Exception:  # noqa: BLE001
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    if os.path.getsize(path) < 100000:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return path


# ---------------------------------------------------------------------------
# FREE ENGINE — per-video unique procedural sad-poetry composer
# ---------------------------------------------------------------------------
def hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _note(midi: float, dur: float, vel: float, amp_env: float = 0.9,
          decay: float = 1.6) -> np.ndarray:
    """Single piano note: attack-decay envelope + 3 partials + gentle detune."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = (
        0.55 * np.sin(2 * np.pi * hz(midi) * t)
        + 0.22 * np.sin(2 * np.pi * hz(midi + 0.02) * 2 * t)
        + 0.09 * np.sin(2 * np.pi * hz(midi) * 3 * t)
    )
    env = np.exp(-t / (dur / 2.5 + decay))
    env *= np.minimum(1.0, t * 60.0)  # soft 17ms attack — no click
    sig = (sig * env * vel * amp_env).astype(np.float32)
    return sig


def _violin_line(midi: float, dur: float, vel: float) -> np.ndarray:
    """Crying violin: sustained note + slow vibrato + warm 2nd partial."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 5.4 + 0.6 * np.sin(2 * np.pi * 0.28 * t)
    sig = 0.65 * np.sin(2 * np.pi * hz(midi) * (t + 0.0014 * np.sin(2 * np.pi * vib * t)))
    sig += 0.25 * np.sin(2 * np.pi * hz(midi) * 2 * t)
    env = np.exp(-t / (dur / 1.8 + 1.1)) * np.clip(t * 2.0, 0, 1) ** 0.7
    return (sig * env * vel * 0.55).astype(np.float32)


def _rain_layer(n: int, gain: float = 0.045) -> np.ndarray:
    """Pink-ish filtered rain noise — gentle, not washing out the piano."""
    white = np.random.uniform(-1, 1, n).astype(np.float32)
    return (np.convolve(white, np.ones(8) / 8.0, mode="same") * gain).astype(np.float32)


def _reverb(sig: np.ndarray, wet: float = 0.26) -> np.ndarray:
    """Simple two-tap comb reverb — the 'slowed + reverb' viral texture."""
    wet_sig = (
        0.30 * np.roll(sig, int(0.053 * SR))
        + 0.18 * np.roll(sig, int(0.111 * SR))
        + 0.10 * np.roll(sig, int(0.197 * SR))
    )
    return sig + wet * wet_sig



# Emotional minor-key progressions (MIDI roots). Each generation picks one
# at random — a fresh harmonic feel every video.
_PROGRESSIONS = [
    # Dm - Bb - F - C  (the classic sad-pop progression)
    [(50, [50, 53, 57, 60]), (46, [46, 50, 53, 57]), (53, [53, 57, 60, 64]), (55, [55, 58, 62, 65])],
    # Am - F - C - G  (heartbreak ballad)
    [(45, [45, 48, 52, 57]), (41, [41, 45, 48, 52]), (48, [48, 52, 55, 60]), (50, [50, 54, 57, 60])],
    # Em - C - G - D   (weeping, cinematic)
    [(52, [52, 55, 59, 64]), (48, [48, 52, 55, 60]), (55, [55, 59, 62, 67]), (50, [50, 54, 57, 62])],
    # Bm - G - D - A   (deep night sadness)
    [(47, [47, 50, 54, 59]), (43, [43, 47, 50, 55]), (50, [50, 54, 57, 62]), (45, [45, 49, 52, 57])],
]


def compose_unique_track(theme: str = "", target_duration: float = 60.0,
                         seed: int = None) -> str | None:
    """Generate a fully UNIQUE sad-poetry bed for one video (free engine).
    Returns the WAV path or None on failure."""
    import logging
    logger = logging.getLogger("music_generator")
    rng = random.Random(seed if seed is not None else int(time.time() * 1000) % (2 ** 31))

    # Unique identity: theme text + day + random salt -> this video's track
    salt = rng.randint(0, 10 ** 9)
    identity = hashlib.md5(f"{theme}|{salt}".encode()).hexdigest()[:8]

    try:
        total_s = max(25.0, min(target_duration + 2.0, 180.0))
        prog = rng.choice(_PROGRESSIONS)
        bpm = rng.uniform(52.0, 68.0)
        beat = 60.0 / bpm
        bar = beat * 4
        n_bars = max(4, int(np.ceil(total_s / bar)))
        total_s = n_bars * bar

        chord_dur = bar * 2  # each chord holds 2 bars (slow, sad pacing)
        bars_per_chord = 2
        melody = []          # (start_t, midi, dur, vel)
        for bi in range(0, n_bars, bars_per_chord):
            root, chord = prog[(bi // bars_per_chord) % len(prog)]
            # piano melody: picks from the chord tones + neighbor note,
            # with human timing jitter (no robotic grid)
            t0 = bi * bar + beat * rng.uniform(0.05, 0.35)
            notes_in_bar = rng.choice([3, 4, 5])
            for k in range(notes_in_bar):
                midi = rng.choice(chord + [chord[0] + 2])
                dur = beat * rng.uniform(0.5, 1.3)
                vel = rng.uniform(0.45, 0.85)
                melody.append((t0, midi, dur, vel))
                t0 += beat * rng.uniform(0.55, 1.1)
                if t0 >= (bi + bars_per_chord) * bar:
                    break

        n = int(total_s * SR)
        sig = np.zeros(n, dtype=np.float32)

        # Piano pass
        for start, midi, dur, vel in melody:
            if start + dur > total_s:
                continue
            ns = _note(midi, dur, vel)
            i0 = int(start * SR)
            i1 = min(n, i0 + len(ns))
            sig[i0:i1] += ns[: i1 - i0]

        # Violin counter-line: one long crying note per chord, slightly late
        for bi in range(0, n_bars, bars_per_chord):
            root, chord = prog[(bi // bars_per_chord) % len(prog)]
            start = bi * bar + beat * 2.2 + rng.uniform(0.0, 0.4)
            midi = rng.choice([chord[1], chord[2]]) + 12
            dur = min(bar * 1.6, total_s - start)
            if dur <= 0.5:
                continue
            vl = _violin_line(midi, dur, rng.uniform(0.35, 0.55))
            i0 = int(start * SR)
            i1 = min(n, i0 + len(vl))
            sig[i0:i1] += vl[: i1 - i0] * 0.8

        # Rain ambience + reverb
        sig = sig * 0.9
        sig += _rain_layer(n)
        sig = _reverb(sig)
        sig /= max(np.abs(sig).max() + 1e-6, 1.0) * 1.15  # headroom

        # Loop-friendly tail: 1.2 s fade-out
        tail = int(1.2 * SR)
        sig[-tail:] *= np.linspace(1.0, 0.0, tail).astype(np.float32)

        # Save
        os.makedirs(BASE_VAULT, exist_ok=True)
        slug = re.sub(r"[^\w]+", "_", theme or "dard")[:26]
        path = os.path.join(BASE_VAULT, f"free_sad_{slug}_{identity}.wav")
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((sig * 32767).astype(np.int16).tobytes())
        logger.info("Free engine: unique track %s (%.0fs, %s, %.0f BPM)",
                    os.path.basename(path), total_s, theme or "sad", bpm)
        return path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Free engine failed (%s) — falling back to stock vault", exc)
        return None


# ---------------------------------------------------------------------------
# Public entry — priority chain: ModelsLab (if key) -> free engine -> stock
# ---------------------------------------------------------------------------
def pick_track(theme: str = "", target_duration: float = 0.0) -> str | None:
    """Return the best available BGM for a video, never blocking the render.

    1. ModelsLab premium AI track (only if MODELSLAB_API_KEY secret is set)
    2. FREE per-video unique procedural track (no key needed)
    3. Legacy mood-picked stock track (last resort)
    """
    gen = generate_sad_music(theme=theme, duration=max(20, int(target_duration)))
    if gen:
        return gen
    free = compose_unique_track(theme=theme, target_duration=max(30.0, target_duration))
    if free:
        return free
    from video_editor import _pick_music  # legacy mood selection
    return _pick_music(theme=theme)
