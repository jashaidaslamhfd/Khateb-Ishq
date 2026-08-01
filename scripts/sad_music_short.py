#!/usr/bin/env python3
"""Khateb-Ishq — DAILY SAD BACKGROUND MUSIC shorts (1–2 min, 100% original).

Owner decision 2026-07-26: "poetry ki bajay abi ke lie 1-2 min ka sad
background music upload karwain, jo copyright free ho".

Every track below is SYNTHESIZED NOTE-BY-NOTE with numpy in this file — no
samples, no loops, no downloaded audio, no external API. The output is an
original composition of this channel by construction, so it is copyright-
free in the strongest possible sense: nothing exists to claim. Viewers may
reuse it with credit — which is also the search hook ("copyright free sad
background music").

Daily pipeline (default mode):
  1. compose today's unique instrumental (mood rotation + date-seeded melody)
  2. build 3 moody stills (AI providers first, procedural cinematic fallback)
  3. title card (PIL, Urdu) + slow-zoom slideshow via ffmpeg, loudnorm -14 LUFS
  4. upload via the same uploader as poetry (private → publishAt snaps to the
     next Pakistan peak slot)
  5. persist data/music_state.json (rotation + dedupe ledger)

Preview mode (no APIs, no upload):
  python scripts/sad_music_short.py --sample /tmp/preview.mp3 --seconds 95
  python scripts/sad_music_short.py --dry            # full video, no upload
"""

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import random
import subprocess
import sys
import wave

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sad-music")

SR = 44100  # full quality for a music-first video (beds under voice use 22050)
STATE_PATH = os.environ.get("MUSIC_STATE_PATH", "data/music_state.json")
OUT = "output"

# ---------------------------------------------------------------------------
# MOODS — daily rotation. Each mood = distinct key, progression, instrument
# colour and ambience, so subscribers never hear "the same track" twice.
# ---------------------------------------------------------------------------
MOODS = [
    {
        "key": "barish_piano_am", "urdu": "بارش اور پیانو", "en": "Rainy Night Piano",
        "bpm": 56, "root": 57, "instrument": "piano",
        "prog": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],  # Am F C G
        "rain": 0.030, "crackle": 0.014, "drone": 0.0,
        "visuals": [
            "rain on a window at night, bokeh city lights, cinematic, no people",
            "wet empty street at night, one street lamp, cinematic, moody",
            "raindrops on glass with distant moonlight, dark cinematic",
        ],
    },
    {
        "key": "raat_drone_em", "urdu": "رات کی دھلان", "en": "Nightfall Drone",
        "bpm": 52, "root": 52, "instrument": "piano",
        "prog": [[52, 55, 59], [48, 52, 55], [55, 59, 62], [57, 60, 64]],  # Em C G Am
        "rain": 0.012, "crackle": 0.0, "drone": 0.10,
        "visuals": [
            "full moon over dark clouds, night sky, cinematic, no people",
            "foggy road disappearing into night, moody cinematic",
            "deserted rooftop at night under moonlight, cinematic",
        ],
    },
    {
        "key": "judai_plucks_dm", "urdu": "جدائی کی دھن", "en": "Farewell Plucks",
        "bpm": 60, "root": 50, "instrument": "pluck",
        "prog": [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]],  # Dm Bb F C
        "rain": 0.0, "crackle": 0.016, "drone": 0.0,
        "visuals": [
            "empty bench in autumn park at dusk, cinematic, melancholic",
            "falling autumn leaves over an old wooden door, cinematic",
            "lone withered tree in evening mist, cinematic, no people",
        ],
    },
    {
        "key": "yaadein_piano_fm", "urdu": "پرانی یادیں", "en": "Old Memories Piano",
        "bpm": 56, "root": 53, "instrument": "piano",
        "prog": [[53, 57, 60], [57, 60, 64], [50, 53, 57], [48, 52, 55]],  # F Am Dm C
        "rain": 0.0, "crackle": 0.020, "drone": 0.0,
        "visuals": [
            "old photo album and candle in a dark room, cinematic",
            "vintage letters and dried rose on wooden table, moody light",
            "curtain moving gently in a dim nostalgic room, cinematic",
        ],
    },
]


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _fade_env(n: int, attack_s: float, release_s: float) -> np.ndarray:
    env = np.ones(n)
    a = min(int(SR * attack_s), n // 2)
    r = min(int(SR * release_s), n // 2)
    if a > 0:
        env[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 0:
        env[-r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return env


def piano_note(midi: int, dur: float, vel: float = 1.0) -> np.ndarray:
    """Soft felt-piano voice: 4 partials, fast attack, long exponential decay."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = (np.sin(2 * np.pi * f * t)
           + 0.55 * np.sin(2 * np.pi * 2 * f * t)
           + 0.22 * np.sin(2 * np.pi * 3 * f * t)
           + 0.08 * np.sin(2 * np.pi * 4 * f * t))
    attack = max(2, int(SR * 0.004))
    env = np.exp(-t / (dur * 0.34))
    env[:attack] = np.linspace(0, 1, attack)
    return (sig * env * vel).astype(np.float64) / 1.85


def pluck_note(midi: int, dur: float, vel: float = 1.0) -> np.ndarray:
    """Karplus-Strong string pluck — nylon guitar-ish, very 'judai'."""
    n = int(SR * dur)
    f = hz(midi)
    buf_len = max(4, int(SR / f))
    buf = np.random.uniform(-1, 1, buf_len)
    out = np.empty(n)
    idx = 0
    for i in range(n):
        cur = buf[idx]
        nxt = buf[(idx + 1) % buf_len]
        new = 0.996 * 0.5 * (cur + nxt)
        buf[idx] = new
        out[i] = cur
        idx = (idx + 1) % buf_len
    attack = max(2, int(SR * 0.003))
    out[:attack] *= np.linspace(0, 1, attack)
    return out * vel


def pad_chord(midis, dur: float, gain: float = 1.0) -> np.ndarray:
    """Wide soft pad: detuned stereo sines + octave shimmer."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    left, right = np.zeros(n), np.zeros(n)
    for m in midis:
        f = hz(m)
        left += np.sin(2 * np.pi * f * 0.999 * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t)
        right += np.sin(2 * np.pi * f * 1.001 * t) + 0.28 * np.sin(2 * np.pi * 2.002 * f * t)
    env = _fade_env(n, min(1.4, dur * 0.3), min(1.6, dur * 0.4))
    return np.stack([left * env, right * env]) * gain / (1.6 * len(midis))


def bass_note(midi: int, dur: float, vel: float = 1.0) -> np.ndarray:
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 0.5 * f * t)
    env = _fade_env(n, 0.25, min(1.0, dur * 0.4))
    return sig * env * vel / 1.25


def rain_layer(n: int, gain: float, rng: np.random.Generator) -> np.ndarray:
    if gain <= 0:
        return np.zeros((2, n))
    noise = rng.standard_normal((2, n))
    alpha = 0.06
    out = np.zeros_like(noise)
    acc = np.zeros(2)
    for i in range(n):
        acc = acc + alpha * (noise[:, i] - acc)
        out[:, i] = acc
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * np.arange(n) / SR / 22.0)
    return out * lfo * gain * 6.0


def crackle_layer(n: int, gain: float, rng: np.random.Generator) -> np.ndarray:
    if gain <= 0:
        return np.zeros(n)
    out = np.zeros(n)
    hits = int(n / SR * 6.5)
    for _ in range(hits):
        pos = int(rng.uniform(0, n - int(SR * 0.004)))
        ln = int(SR * rng.uniform(0.0005, 0.003))
        out[pos:pos + ln] += rng.uniform(-1, 1) * np.linspace(1, 0, ln)
    return out * gain * 0.9


def drone_layer(midis, n: int, gain: float) -> np.ndarray:
    if gain <= 0:
        return np.zeros(n)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for m in midis:
        f = hz(m)
        sig += np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 1.005 * t)
    return sig * gain / (2.0 * len(midis))


def _pentatonic(root: int) -> list:
    return [root + step for step in (0, 3, 5, 7, 10, 12, 15, 17, 19, 22, 24)]


def _melody(rng: random.Random, mood: dict, total_bars: int, intro_s: float) -> list:
    """Note-by-note sad melody over the mood's pentatonic. AABA phrase
    structure with a long root resolution at the end — composed, not random."""
    pent = _pentatonic(mood["root"])
    spb = 60.0 / mood["bpm"]
    bar_s = 4 * spb
    idx = rng.randint(2, 5)
    notes = []
    patterns = [
        [(0, 4), (4, 2), (6, 2)],          # half, quarter, quarter
        [(0, 2), (2, 2), (4, 2), (6, 2)],  # walk
        [(0, 4), (4, 4)],                  # breathing holds
        [(0, 2), (2, 1), (3, 1), (4, 2), (6, 2)],
        [(0, 8)],                          # whole-bar note
    ]
    for bar in range(total_bars):
        is_last = bar >= total_bars - 2
        pattern = [(0, 16 if is_last and bar == total_bars - 1 else 8)] if is_last else rng.choice(patterns)
        if not is_last and rng.random() < 0.12:
            continue  # a full bar of silence — suspense is part of sad music
        for slot_e, len_e in pattern:
            t0 = intro_s + bar * bar_s + slot_e / 2 * spb
            dur = max(0.9 * (len_e / 2) * spb, 0.22)
            if is_last:
                midi = mood["root"] + 12
            else:
                step = rng.choice((-2, -1, -1, 1, 1, 2))
                idx = max(1, min(len(pent) - 2, idx + step))
                midi = pent[idx]
            vel = 0.62 + 0.38 * rng.random()
            if slot_e == 0:
                vel = min(1.0, vel + 0.12)  # down-beat accent
            notes.append((t0, min(dur, 2.4), midi, vel))
    return notes


def compose_music(mood: dict, seconds: float, seed: int) -> np.ndarray:
    """Full arrangement -> stereo float array in [-1, 1]."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    np.random.seed(seed % (2 ** 31))  # pads/plucks use global np.random
    spb = 60.0 / mood["bpm"]
    intro_s = 4.0
    body_s = seconds - intro_s - 6.0
    total_bars = max(8, int(round(body_s / (4 * spb))))
    n = int(SR * seconds)
    left = np.zeros(n)
    right = np.zeros(n)
    mono = np.zeros(n)

    # --- pads + bass per chord ---
    bar = 0
    i = 0
    while bar < total_bars:
        chord = mood["prog"][i % len(mood["prog"])]
        t0 = intro_s + bar * 4 * spb
        dur_bar = 4 * spb
        start = int(t0 * SR)
        if start >= n:
            break
        pad = pad_chord(chord, dur_bar, gain=0.9)
        ln = min(pad.shape[1], n - start)
        left[start:start + ln] += pad[0, :ln] * 0.30
        right[start:start + ln] += pad[1, :ln] * 0.30
        bn = bass_note(chord[0] - 12, min(dur_bar, 2.2), vel=0.9)
        lb = min(len(bn), n - start)
        mono[start:start + lb] += bn[:lb] * 0.26
        bar += 1
        i += 1

    # --- melody ---
    voice = pluck_note if mood["instrument"] == "pluck" else piano_note
    for t0, dur, midi, vel in _melody(rng, mood, total_bars, intro_s):
        start = int(t0 * SR)
        if start >= n:
            continue
        note = voice(midi, dur, vel)
        stereo_w = voice(midi, dur, vel * 0.35) if mood["instrument"] == "piano" else note * 0.3
        ln = min(len(note), n - start)
        left[start:start + ln] += note[:ln] * 0.34
        right[start:start + ln] += stereo_w[:ln] * 0.34

    # --- ambience ---
    rain = rain_layer(n, mood["rain"], np_rng)
    left += rain[0]
    right += rain[1]
    crackle = crackle_layer(n, mood["crackle"], np_rng)
    left += crackle * 0.7
    right += crackle * 0.7
    mono += drone_layer([mood["prog"][0][0] - 24], n, mood["drone"])

    left += mono
    right += mono

    # --- master: soft clip, fades, normalize ---
    mix = np.stack([left, right])
    mix = np.tanh(mix * 0.9)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.92
    fade_in = int(SR * 1.5)
    fade_out = int(SR * 5.0)
    mix[:, :fade_in] *= np.linspace(0, 1, fade_in)
    mix[:, -fade_out:] *= np.linspace(1, 0, fade_out)
    return mix


def _write_wav(path: str, mix: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pcm = np.clip(mix.T * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _to_mp3(wav_path: str, mp3_path: str) -> str:
    try:
        subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame",
                        "-q:a", "3", mp3_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return mp3_path
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", wav_path,
                        "-codec:a", "libmp3lame", "-q:a", "3", mp3_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return mp3_path
    except Exception:
        return wav_path


# ---------------------------------------------------------------------------
# DAILY SELECTION — mood rotation + date-seeded composition (unique per day)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)


def pick_today(state: dict) -> tuple:
    today = dt.date.today()
    mood_idx = int(state.get("mood_idx", -1)) + 1
    if state.get("last_date") != today.isoformat() or mood_idx >= len(MOODS):
        mood_idx = mood_idx % len(MOODS)
    mood = MOODS[mood_idx % len(MOODS)]
    seed = today.toordinal() * 1000 + mood_idx
    return mood_idx, mood, seed, today


# ---------------------------------------------------------------------------
# VISUALS — AI providers first (same generator as poetry), procedural
# cinematic backdrops as a guaranteed fallback so the channel never breaks.
# ---------------------------------------------------------------------------

def _procedural_backdrop(path: str, mood: dict, seed: int) -> str:
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    palettes = {"barish_piano_am": ((8, 16, 34), (16, 42, 84)),
                "raat_drone_em": ((6, 8, 18), (26, 24, 52)),
                "judai_plucks_dm": ((28, 14, 8), (74, 42, 18)),
                "yaadein_piano_fm": ((24, 10, 20), (64, 30, 44))}
    top, bottom = palettes.get(mood["key"], ((10, 10, 16), (30, 30, 46)))
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        f = y / H
        c = tuple(int(top[k] + (bottom[k] - top[k]) * f) for k in range(3))
        for x in range(0, W, 4):
            for xx in range(x, min(x + 4, W)):
                px[xx, y] = c
    overlay = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(overlay)
    for _ in range(26):  # soft bokeh light circles
        r = rng.randint(18, 90)
        x, y = rng.randint(0, W), rng.randint(0, H)
        warm = rng.choice([(255, 200, 120), (160, 190, 255), (255, 160, 140)])
        dr.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * 0.25) for v in warm))
    overlay = overlay.filter(ImageFilter.GaussianBlur(42))
    img = Image.blend(img, Image.composite(overlay, img, overlay.convert("L").point(lambda v: min(160, v))), 0.5)
    vign = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([-W * 0.25, -H * 0.2, W * 1.25, H * 1.15], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(220))
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vign)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path, quality=92)
    return path


def _get_stills(mood: dict, seed: int) -> list:
    paths = []
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    try:
        from image_generator import generate_scene_image
        used = set()
        for i, visual in enumerate(mood["visuals"]):
            try:
                res = generate_scene_image(i, {"visual": visual, "caption": ""}, used, set())
                if res and res.get("path") and os.path.exists(res["path"]):
                    paths.append(res["path"])
            except Exception as exc:
                log.warning("AI still %d failed (%s) — procedural fallback", i + 1, exc)
    except Exception as exc:
        log.warning("image_generator unavailable (%s) — full procedural set", exc)
    while len(paths) < 3:
        paths.append(_procedural_backdrop(f"{OUT}/stills/proc_{len(paths)}.jpg", mood, seed + len(paths)))
    return paths[:3]


def _make_title_card(mood: dict, seed: int) -> str:
    """1080x1920 opening card: procedural backdrop + Urdu mood title."""
    path = _procedural_backdrop(f"{OUT}/card_base.jpg", mood, seed + 777)
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font_path = None
    for cand in ("assets/fonts/NotoNaskhArabic-Bold.ttf",
                 "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"):
        if os.path.exists(cand):
            font_path = cand
            break
    if font_path:
        font = ImageFont.truetype(font_path, 120)
        text = mood["urdu"]
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            text = get_display(arabic_reshaper.reshape(text))
        except Exception:
            pass
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((1080 - tw) / 2, 780 - th / 2), text, font=font, fill=(240, 236, 228))
        except Exception:
            pass
    label = "ORIGINAL • COPYRIGHT FREE"
    latin_font = None
    for cand in ("assets/fonts/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cand):
            latin_font = ImageFont.truetype(cand, 40)
            break
    if latin_font:
        bbox = draw.textbbox((0, 0), label, font=latin_font)
        draw.text(((1080 - (bbox[2] - bbox[0])) / 2, 1000), label, font=latin_font, fill=(200, 190, 170))
        line2 = "Khateb-e-Ishq | free to use with credit"
        bbox2 = draw.textbbox((0, 0), line2, font=latin_font)
        draw.text(((1080 - (bbox2[2] - bbox2[0])) / 2, 1720), line2, font=latin_font, fill=(170, 165, 155))
    img.save(f"{OUT}/card.jpg", quality=92)
    return f"{OUT}/card.jpg"


# ---------------------------------------------------------------------------
# VIDEO BUILD — pure ffmpeg (zoompan slideshow + loudnorm), no moviepy.
# ---------------------------------------------------------------------------

def _build_video(stills: list, card: str, wav_path: str, seconds: float, out_path: str) -> str:
    card_s = 4.5
    body = seconds - card_s
    seg_s = body / len(stills)
    frames_seg = int(seg_s * 30)
    frames_card = int(card_s * 30)
    os.makedirs(f"{OUT}/segments_music", exist_ok=True)
    segs = []

    def zoom_cmd(src, dst, frames, direction):
        if direction == "in":
            z = "min(1.05+0.00045*on,1.16)"
        else:
            z = "max(1.16-0.00045*on,1.05)"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", src,
            "-vf", ("scale=1188:2112:force_original_aspect_ratio=increase,crop=1188:2112,"
                    f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,"
                    "format=yuv420p"),
            "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", dst,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    zoom_cmd(card, f"{OUT}/segments_music/seg0.mp4", frames_card, "in")
    segs.append(f"{OUT}/segments_music/seg0.mp4")
    for i, still in enumerate(stills, start=1):
        zoom_cmd(still, f"{OUT}/segments_music/seg{i}.mp4", frames_seg, "in" if i % 2 else "out")
        segs.append(f"{OUT}/segments_music/seg{i}.mp4")

    concat_list = f"{OUT}/segments_music/concat.txt"
    with open(concat_list, "w") as fh:
        for seg in segs:
            fh.write(f"file '{os.path.abspath(seg)}'\n")
    muted = f"{OUT}/segments_music/muted.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                    "-c", "copy", muted], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fade_start = max(0.0, seconds - 4.5)
    subprocess.run([
        "ffmpeg", "-y", "-i", muted, "-i", wav_path,
        "-vf", f"fade=t=in:st=0:d=1.2,fade=t=out:st={fade_start:.1f}:d=4.0,format=yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart", out_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log.info("video built: %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="music-only preview file (.wav or .mp3); no APIs, no upload")
    ap.add_argument("--seconds", type=float, default=float(os.environ.get("MUSIC_SECONDS", "95")),
                    help="track length (1-2 min per owner)")
    ap.add_argument("--mood", help="force mood key (default: daily rotation)")
    ap.add_argument("--seed", type=int, help="force composition seed")
    ap.add_argument("--dry", action="store_true", help="build everything, skip upload")
    args = ap.parse_args()

    seconds = max(60.0, min(115.0, args.seconds))  # owner asked for 1-2 minutes

    state = _load_state()
    if args.mood:
        mood_idx = next((i for i, m in enumerate(MOODS) if m["key"] == args.mood), 0)
        mood = MOODS[mood_idx]
        seed = args.seed if args.seed is not None else 424242
    else:
        mood_idx, mood, seed, _today = pick_today(state)
        if args.seed is not None:
            seed = args.seed

    fingerprint = hashlib.sha256(f"{mood['key']}|{seed}".encode()).hexdigest()[:16]
    log.info("mood=%s seed=%d fingerprint=%s seconds=%.0f", mood["key"], seed, fingerprint, seconds)

    # 1) compose
    mix = compose_music(mood, seconds, seed)
    if args.sample:
        if args.sample.lower().endswith(".mp3"):
            wav_tmp = "output/_sample_tmp.wav" if not args.sample.startswith("/") else args.sample + ".wav"
            _write_wav(wav_tmp, mix)
            out = _to_mp3(wav_tmp, args.sample)
            log.info("sample ready: %s", out)
        else:
            _write_wav(args.sample, mix)
            log.info("sample ready: %s", args.sample)
        return 0

    wav_path = f"{OUT}/music_{fingerprint}.wav"
    _write_wav(wav_path, mix)

    # 2) visuals + card
    stills = _get_stills(mood, seed)
    card = _make_title_card(mood, seed)

    # 3) video + thumbnail
    video_path = _build_video(stills, card, wav_path, seconds, f"{OUT}/music_video_{fingerprint}.mp4")
    thumb_path = card  # the designed opening card doubles as the thumbnail

    script_data = {
        "kind": "music",
        "title": f"{mood['en']} | Sad Background Music Copyright Free | USE in Your Videos",
        "poet": "Original",
        "description": (f"{mood['urdu']} — {mood['en']}. Aik original sad instrumental, "
                        "Khateb-e-Ishq ki apni composition — moody, soft, aur bilkul copyright-free."),
        "tags": ["sad background music", "copyright free music", "royalty free music",
                 "sad piano", "background music", "dukhi status", "urdu", mood["key"]],
    }

    if args.dry:
        log.info("DRY RUN — skipping upload. video=%s thumb=%s", video_path, thumb_path)
        return 0

    # 4) upload via the same proven uploader (private → next PK peak slot)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from uploader import upload_all
    result = upload_all(video_path, thumb_path, script_data)
    log.info("upload result: %s", result)

    # 5) persist rotation + ledger
    state = _load_state()
    history = state.get("history", [])
    history.append({
        "fingerprint": fingerprint, "mood": mood["key"], "seed": seed,
        "title": script_data["title"], "seconds": seconds,
        "date": dt.date.today().isoformat(),
        "youtube_video_id": (result or {}).get("youtube_video_id"),
        "publish_at": (result or {}).get("publish_at"),
    })
    state.update({"mood_idx": mood_idx, "last_date": dt.date.today().isoformat(),
                  "history": history[-120:]})
    _save_state(state)
    return 0 if (result or {}).get("youtube_success") else 1


if __name__ == "__main__":
    sys.exit(main())
