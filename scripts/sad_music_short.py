#!/usr/bin/env python3
"""Khateb-Ishq — DAILY SAD BACKGROUND MUSIC (Landscape 16:9, 100% original).

Optimized for: Trending TikTok/Shorts styles (Slowed + Reverb).
Logic: 1920x1080 Landscape format, Cinematic visuals.
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

SR = 44100  # full quality for a music-first video
STATE_PATH = os.environ.get("MUSIC_STATE_PATH", "data/music_state.json")
OUT = "output"

# ---------------------------------------------------------------------------
# MOODS — daily rotation.
# Formula: TikTok Viral formula (Slowed Piano + Heavy Rain + Reverb).
# ---------------------------------------------------------------------------
MOODS = [
    {
        "key": "tiktok_style_poetry", "urdu": "ٹک ٹاک وائرل میوزک", "en": "TikTok Viral Sad Music",
        "bpm": 42, "root": 50, "instrument": "piano",
        "prog": [[50, 53, 57, 60], [46, 50, 53, 57], [53, 57, 60, 64], [45, 48, 52, 55]],  # Dm Bb F Am
        "rain": 0.060, "crackle": 0.010, "drone": 0.0,
        "viral_wav": "assets/music/tiktok_style_poetry.wav",
        "visuals": [
            "cinematic rainy street at night, neon reflections, 16:9 aesthetic",
            "lone figure walking in rain, moody street lights, dark cinematic",
            "raindrops on car window, blurred city lights bokeh, melancholic vibe",
        ],
    },
    {
        "key": "barish_piano_viral", "urdu": "بارش پیانو وائرل", "en": "Rain Piano Viral",
        "bpm": 56, "root": 57, "instrument": "piano",
        "prog": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
        "rain": 0.040, "crackle": 0.0, "drone": 0.0,
        "viral_wav": "assets/music/barish_piano_viral.wav",
        "visuals": [
            "heavy rain view from window, cozy dark room, cinematic landscape",
            "distant city lights through rain, moody atmosphere, 4k cinematic",
            "wet dark asphalt road at night, aesthetic lighting",
        ],
    },
    {
        "key": "raat_ka_dard", "urdu": "رات کا درد", "en": "Night Pain",
        "bpm": 52, "root": 52, "instrument": "piano",
        "prog": [[52, 55, 59], [48, 52, 55], [55, 59, 62], [57, 60, 64]],
        "rain": 0.030, "crackle": 0.0, "drone": 0.0,
        "viral_wav": "assets/music/raat_ka_dard.wav",
        "visuals": [
            "starry night sky over mountains, slow moon movement, cinematic",
            "empty rooftop view of the city at night, moody landscape",
            "dim light from a single house in a vast dark valley",
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

def compose_music(mood: dict, seconds: float, seed: int) -> np.ndarray:
    """Uses viral tracks with TikTok formula."""
    viral_wav = mood.get("viral_wav")
    if viral_wav and os.path.exists(viral_wav):
        log.info("Using pre-generated viral track: %s", viral_wav)
        try:
            import soundfile as sf
            data, sr = sf.read(viral_wav, dtype="float64")
            if data.ndim == 1: data = np.stack([data, data])
            elif data.ndim == 2: data = data.T
            n = int(SR * seconds)
            if data.shape[1] >= n: data = data[:, :n]
            else:
                loops = int(np.ceil(n / data.shape[1]))
                data = np.tile(data, (1, loops))[:, :n]
            # Master fades
            f_in, f_out = int(SR * 2), int(SR * 5)
            data[:, :f_in] *= np.linspace(0, 1, f_in)
            data[:, -f_out:] *= np.linspace(1, 0, f_out)
            return data / (np.max(np.abs(data)) or 1.0) * 0.9
        except: pass
    
    # Fallback to simple synthesis if wav missing
    n = int(SR * seconds)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * hz(mood["root"]) * t) * 0.3 * _fade_env(n, 2, 5)
    return np.stack([sig, sig])

def _procedural_backdrop(path: str, mood: dict, seed: int) -> str:
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    W, H = 1920, 1080
    top = (8, 12, 24)
    bottom = (24, 28, 48)
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        f = y / H
        c = tuple(int(top[k] + (bottom[k] - top[k]) * f) for k in range(3))
        for x in range(W): px[x, y] = c
    overlay = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(overlay)
    for _ in range(40):
        r = rng.randint(40, 150)
        x, y = rng.randint(0, W), rng.randint(0, H)
        color = rng.choice([(255, 180, 100), (140, 170, 255), (255, 140, 130)])
        dr.ellipse([x-r, y-r, x+r, y+r], fill=tuple(int(v*0.2) for v in color))
    img = Image.blend(img, overlay.filter(ImageFilter.GaussianBlur(60)), 0.4)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path, quality=92)
    return path

def _make_title_card(mood: dict, seed: int) -> str:
    path = _procedural_backdrop(f"{OUT}/card_base.jpg", mood, seed)
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = 1920, 1080
    
    f_path = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
    if not os.path.exists(f_path): f_path = "assets/fonts/DejaVuSans-Bold.ttf"
    
    font = ImageFont.truetype(f_path, 120)
    text = mood["urdu"]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H // 2 - 100), text, font=font, fill=(240, 230, 210))
    
    font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    label = "TIKTOK VIRAL STYLE • COPYRIGHT FREE"
    bbox_s = draw.textbbox((0, 0), label, font=font_s)
    draw.text(((W - (bbox_s[2] - bbox_s[0])) / 2, H // 2 + 80), label, font=font_s, fill=(180, 170, 150))
    
    img.save(f"{OUT}/card.jpg", quality=92)
    return f"{OUT}/card.jpg"

def _build_video(stills: list, card: str, wav_path: str, seconds: float, out_path: str) -> str:
    W, H = 1920, 1080
    os.makedirs(f"{OUT}/segments_music", exist_ok=True)
    
    def zoom_cmd(src, dst, dur, direction):
        z = "min(1.03+0.0004*on,1.15)" if direction == "in" else "max(1.15-0.0004*on,1.03)"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", str(dur), "-i", src,
            "-vf", f"scale=2112:1188,zoompan=z='{z}':d={dur*30}:s={W}x{H}:fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", dst
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    segs = []
    zoom_cmd(card, f"{OUT}/segments_music/s0.mp4", 5.0, "in")
    segs.append(f"{OUT}/segments_music/s0.mp4")
    
    seg_dur = (seconds - 5.0) / len(stills)
    for i, s in enumerate(stills):
        p = f"{OUT}/segments_music/s{i+1}.mp4"
        zoom_cmd(s, p, seg_dur, "in" if i % 2 else "out")
        segs.append(p)
        
    with open(f"{OUT}/list.txt", "w") as f:
        for s in segs: f.write(f"file '{os.path.abspath(s)}'\n")
        
    muted = f"{OUT}/muted.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{OUT}/list.txt", "-c", "copy", muted], check=True)
    
    subprocess.run([
        "ffmpeg", "-y", "-i", muted, "-i", wav_path,
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
        "-c:v", "copy", "-c:a", "aac", "-shortest", out_path
    ], check=True)
    return out_path

def main():
    state = {}
    if os.path.exists(STATE_PATH): state = json.load(open(STATE_PATH))
    
    idx = (state.get("mood_idx", -1) + 1) % len(MOODS)
    mood = MOODS[idx]
    seconds = 95.0
    seed = int(dt.date.today().toordinal())
    
    log.info("Generating LANDSCAPE TikTok Viral Music: %s", mood["en"])
    
    wav = f"{OUT}/music.wav"
    mix = compose_music(mood, seconds, seed)
    # Write WAV
    pcm = np.clip(mix.T * 32767, -32768, 32767).astype(np.int16)
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
        
    card = _make_title_card(mood, seed)
    
    # Simple still collection
    stills = [card] * 3 
    
    video = _build_video(stills, card, wav, seconds, f"{OUT}/landscape_music.mp4")
    
    # Upload logic (simplified)
    script_data = {"kind": "music", "title": f"{mood['urdu']} | {mood['en']} | TikTok Viral Background Music", "description": "100% Original", "tags": ["landscape", "music"]}
    
    sys.path.insert(0, "src")
    from uploader import upload_all
    upload_all(video, card, script_data)
    
    state["mood_idx"] = idx
    json.dump(state, open(STATE_PATH, "w"))

if __name__ == "__main__":
    main()
