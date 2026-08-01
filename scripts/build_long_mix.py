#!/usr/bin/env python3
"""Long Mix Video Builder — 8-10 minute compilation for watch hours.

This is the KEY to reaching 4,000 watch hours for monetization.
Current: 509 hours. Need: 3,491 more.

Strategy:
  - Combine 5-6 poetry shorts into one 8-10 minute video
  - Each video can generate 8-10 watch hours per view
  - 500 views = ~66.7 hours per video
  - Need ~52 such videos = ~2 per day

Usage:
  python scripts/build_long_mix.py
  python scripts/build_long_mix.py --count 5  # build 5 mixes
"""

import json
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("long-mix")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = "output"

# ── Long Mix Configuration ────────────────────────────────────────────────
MIX_DURATION_MIN = 480   # 8 minutes minimum
MIX_DURATION_MAX = 600   # 10 minutes maximum
MIX_TITLE_TEMPLATES = [
    "Sad Poetry Mix {n} | Heart Touching Shayari | Background Music",
    "Dard Bhari Shayari Collection {n} | Sad Urdu Poetry | BG Music",
    "Urdu Sad Poetry Compilation {n} | Emotional Shayari | Poetry Background Music",
    "Gham Ki Shayari Mix {n} | Sad Background Music | Heart Touching",
    "Best Sad Poetry Collection {n} | Urdu Shayari | Background Music for Poetry",
    "Sad Shayari Mixtape {n} | Dard Bhari | Poetry Background Music",
    "Emotional Poetry Mix {n} | Sad Urdu | Background Music Poetry",
    "Heart Breaking Poetry {n} | Sad Shayari | Poetry BG Music",
    "Rula Dene Wali Shayari {n} | Sad Poetry | Background Music",
    "Deep Sad Poetry Collection {n} | Urdu | Copyright Free Background Music",
]

MIX_DESCRIPTION = """🎵 Sad Poetry Mix with Background Music — Khateb-e-Ishq

Yeh video mein kayi emotional Urdu shayari hain with sad background music.
Har shayari dil ko chhoo legi — sunte rahiye!

📌 SUBSCRIBE for daily sad poetry with background music
🎵 Music: 100% Original & Copyright-Free (Khateb-e-Ishq composition)

✅ Free to use with credit: 'Music: Khateb-e-Ishq (YouTube)'

#poetrybackgroundmusic #sadshayaribackgroundmusic #backgroundmusicforpoetry
#poetrybgmusic #sadbackgroundmusic #copyrightfreebackgroundmusic
#nocopyrightmusic #backgroundmusicpoetry #urdupoetry #sadpoetry #shayari
"""

MIX_TAGS = [
    # Channel's top search terms (real analytics)
    "poetry background music", "sad shayari background music",
    "background music for poetry", "background music poetry",
    "poetry bg music", "sad background music",
    "copyright free background music", "no copyright music",
    # India audience terms (45.6% of viewers)
    "hindi sad poetry", "dard bhari shayari hindi",
    "sad shayari hindi", "heart touching shayari",
    "2 line sad poetry", "urdupoetry", "shayari",
    "sad poetry", "emotional poetry", "gham",
]


def _get_existing_videos() -> list:
    """Get list of existing video files in output/."""
    videos = []
    output_dir = ROOT / "output"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.mp4")):
            if f.stat().st_size > 100_000:  # at least 100KB
                videos.append(str(f))
    return videos


def _create_mix_title(mix_number: int) -> str:
    """Create a mix title from templates."""
    template = MIX_TITLE_TEMPLATES[mix_number % len(MIX_TITLE_TEMPLATES)]
    return template.format(n=mix_number)


def _build_intro_card(title: str, duration_s: float = 5.0) -> str:
    """Create a 1080x1920 intro card with title text."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1080, 1920), (8, 8, 12))
    draw = ImageDraw.Draw(img)

    # Add warm bokeh circles
    rng = random.Random(hash(title))
    for _ in range(8):
        r = rng.randint(80, 250)
        x, y = rng.randint(0, 1080), rng.randint(0, 1920)
        color = rng.choice([(255, 180, 100), (140, 170, 255), (255, 140, 130)])
        draw.ellipse([x-r, y-r, x+r, y+r], fill=tuple(int(v * 0.2) for v in color))

    # Blur
    from PIL import ImageFilter
    img = img.filter(ImageFilter.GaussianBlur(60))

    # Title text
    font = None
    for path in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "assets/fonts/DejaVuSans-Bold.ttf"]:
        if os.path.exists(path):
            font = ImageFont.truetype(path, 52)
            break

    if font:
        # Wrap title
        words = title.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > 980:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        y_start = 800
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((1080 - tw) / 2, y_start), line, font=font, fill=(255, 246, 230),
                     stroke_width=2, stroke_fill=(0, 0, 0))
            y_start += 70

    # Channel branding
    small_font = None
    for path in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "assets/fonts/DejaVuSans.ttf"]:
        if os.path.exists(path):
            small_font = ImageFont.truetype(path, 32)
            break

    if small_font:
        label = "Khateb-e-Ishq • Original • Copyright Free"
        bbox = draw.textbbox((0, 0), label, font=small_font)
        tw = bbox[2] - bbox[0]
        draw.text(((1080 - tw) / 2, 1600), label, font=small_font, fill=(180, 170, 160))

    # Vignette
    from PIL import ImageFilter
    vign = Image.new("L", (1080, 1920), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([-270, -384, 1350, 2304], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(220))
    img = Image.composite(img, Image.new("RGB", (1080, 1920), (0, 0, 0)), vign)

    os.makedirs(f"{OUT}/mix", exist_ok=True)
    path = f"{OUT}/mix/intro_card.jpg"
    img.save(path, quality=92)
    return path


def _build_end_card(duration_s: float = 5.0) -> str:
    """Create a 1080x1920 end card with subscribe CTA."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1080, 1920), (8, 8, 12))
    draw = ImageDraw.Draw(img)

    font = None
    for path in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "assets/fonts/DejaVuSans-Bold.ttf"]:
        if os.path.exists(path):
            font = ImageFont.truetype(path, 64)
            break

    if font:
        lines = [
            "SUBSCRIBE for Daily",
            "Sad Poetry + Background Music",
            "",
            "❤️ Like if this touched your heart",
            "💬 Comment your favorite sher",
        ]
        y = 750
        for line in lines:
            if line:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                draw.text(((1080 - tw) / 2, y), line, font=font, fill=(255, 246, 230),
                         stroke_width=2, stroke_fill=(0, 0, 0))
            y += 85

    os.makedirs(f"{OUT}/mix", exist_ok=True)
    path = f"{OUT}/mix/end_card.jpg"
    img.save(path, quality=92)
    return path


def _build_mix_video(segment_videos: list, mix_number: int, music_path: str = None) -> str:
    """Build a long mix video by concatenating multiple poetry videos with intro/end."""
    os.makedirs(f"{OUT}/mix", exist_ok=True)

    title = _create_mix_title(mix_number)
    intro_card = _build_intro_card(title)
    end_card = _build_end_card()

    # Build intro segment (5s)
    intro_mp4 = f"{OUT}/mix/intro.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", intro_card,
        "-vf", f"scale=1080:1920,zoompan=z='1.05+0.0003*on':d=150:s=1080x1920:fps=30,format=yuv420p",
        "-t", "5", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-an", intro_mp4
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Build end segment (5s)
    end_mp4 = f"{OUT}/mix/end.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", end_card,
        "-vf", f"scale=1080:1920,zoompan=z='1.08-0.0003*on':d=150:s=1080x1920:fps=30,format=yuv420p",
        "-t", "5", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-an", end_mp4
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Concatenate all segments
    concat_list = f"{OUT}/mix/concat.txt"
    with open(concat_list, "w") as fh:
        fh.write(f"file '{os.path.abspath(intro_mp4)}'\n")
        for vid in segment_videos:
            fh.write(f"file '{os.path.abspath(vid)}'\n")
        fh.write(f"file '{os.path.abspath(end_mp4)}'\n")

    # Concat video
    muted = f"{OUT}/mix/muted.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c", "copy", muted
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Add background music
    fingerprint = f"mix_{mix_number}_{int(time.time())}"
    out_path = f"{OUT}/mix_video_{fingerprint}.mp4"

    if music_path and os.path.exists(music_path):
        # Loop music to fill entire video
        subprocess.run([
            "ffmpeg", "-y", "-i", muted, "-stream_loop", "-1", "-i", music_path,
            "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", out_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # Just copy without music
        subprocess.run([
            "ffmpeg", "-y", "-i", muted,
            "-c", "copy", "-movflags", "+faststart", out_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    log.info("Long mix video built: %s", out_path)
    return out_path


def _pick_music() -> str:
    """Pick a music track for the mix."""
    music_dir = ROOT / "assets" / "music"
    if music_dir.exists():
        tracks = list(music_dir.glob("*.wav")) + list(music_dir.glob("*.mp3"))
        if tracks:
            return str(random.choice(tracks))
    return ""


def build_and_upload_mix(mix_number: int = 1) -> dict:
    """Build a long mix video and upload it."""
    from main import run_pipeline
    from uploader import upload_all
    from video_editor import generate_thumbnail

    # Generate 5-6 fresh poetry videos for the mix
    segment_videos = []
    num_segments = 6  # 6 × ~50s = ~300s = 5min + intro/end = ~5.5min

    # To get 8+ minutes, we need more segments or longer poems
    # Let's generate 8-10 segments
    num_segments = 10  # 10 × ~50s = ~500s = ~8.3min

    log.info("Building long mix #%d with %d segments...", mix_number, num_segments)

    # Generate each segment as a separate pipeline run
    for i in range(num_segments):
        log.info("Generating segment %d/%d...", i + 1, num_segments)
        try:
            # Run pipeline for each segment
            result = run_pipeline()
            if result.get("success"):
                video_path = f"{ROOT}/output/final_video.mp4"
                if os.path.exists(video_path):
                    # Copy to a unique name
                    seg_path = f"{OUT}/mix/seg_{i}_{int(time.time())}.mp4"
                    import shutil
                    shutil.copy2(video_path, seg_path)
                    segment_videos.append(seg_path)
                    log.info("  ✅ Segment %d ready", i + 1)
                else:
                    log.warning("  ❌ Segment %d video not found", i + 1)
            else:
                log.warning("  ❌ Segment %d pipeline failed", i + 1)
        except Exception as exc:
            log.warning("  ❌ Segment %d failed: %s", i + 1, exc)

        # Anti-spam: wait between segments
        if i < num_segments - 1:
            time.sleep(2)

    if not segment_videos:
        log.error("No segments generated — cannot build mix")
        return {"success": False, "error": "no segments"}

    # Build the mix video
    music_path = _pick_music()
    mix_video = _build_mix_video(segment_videos, mix_number, music_path)

    # Generate thumbnail
    thumb_path = f"{OUT}/mix/mix_thumb_{mix_number}.jpg"
    if segment_videos and os.path.exists(segment_videos[0]):
        from video_editor import generate_thumbnail
        generate_thumbnail(segment_videos[0], f"Mix #{mix_number}").replace(".jpg", f"_{mix_number}.jpg")
        # Copy the thumbnail
        import shutil
        src_thumb = f"{ROOT}/output/thumbnail.jpg"
        if os.path.exists(src_thumb):
            shutil.copy2(src_thumb, thumb_path)
        else:
            thumb_path = _build_intro_card(_create_mix_title(mix_number))

    # Upload
    script_data = {
        "kind": "mix",
        "title": _create_mix_title(mix_number),
        "poet": "Various",
        "description": MIX_DESCRIPTION,
        "tags": MIX_TAGS,
        "title_roman": _create_mix_title(mix_number),
    }

    try:
        result = upload_all(mix_video, thumb_path, script_data)
        log.info("Upload result: %s", result)
        return {"success": True, "mix_number": mix_number, "result": result}
    except Exception as exc:
        log.error("Upload failed: %s", exc)
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1, help="Number of mixes to build")
    args = ap.parse_args()

    for i in range(1, args.count + 1):
        log.info("=" * 60)
        log.info("BUILDING LONG MIX #%d", i)
        log.info("=" * 60)
        result = build_and_upload_mix(i)
        if result["success"]:
            log.info("✅ Mix #%d uploaded successfully!", i)
        else:
            log.error("❌ Mix #%d failed: %s", i, result.get("error"))
