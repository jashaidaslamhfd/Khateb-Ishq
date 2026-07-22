#!/usr/bin/env python3
"""Poetry Shorts video builder (1080x1920).

Lean by design: Ken-Burns stills + Urdu RTL captions + narration + music bed.
Urdu captions need proper Arabic-script shaping — PIL handles it ONLY via
libraqm (features.check('raqm')). Ubuntu runners: `apt install fonts-noto`
gives NotoNaskhArabic which renders Urdu cleanly.
"""

import glob
import logging
import os
import random
import textwrap

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, features

# --- Pillow >= 10 compatibility: moviepy 1.x's resize fx still reads
# Image.ANTIALIAS, which Pillow 10 removed (2023). Map it to LANCZOS.
# Without this shim every Ken-Burns zoom crashes with:
#   AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 30
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabicUI-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "assets/fonts/NotoNaskhArabic-Bold.ttf",
]
MUSIC_VOLUME = float(os.environ.get("MUSIC_VOLUME", "0.08"))
ZOOM = 1.08  # gentle Ken-Burns max zoom


def _has_raqm() -> bool:
    try:
        return bool(features.check("raqm"))
    except Exception:
        return False


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError(
        "No Urdu-capable font found. Install one (runner: `sudo apt install "
        "fonts-noto` → NotoNaskhArabic-Bold.ttf) or drop it in assets/fonts/."
    )


def _rtl_wrap(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_px: int) -> list:
    """Greedy wrap that measures AFTER raqm shaping (RTL width differs)."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        width = draw.textlength(trial, font=font, direction="rtl", language="ur")
        if width <= max_px or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _compose_caption_image(caption: str) -> Image.Image:
    """Transparent caption strip: centered Urdu text, dark scrim for
    readability, RTL shaping with Urdu language tag."""
    strip = Image.new("RGBA", (WIDTH, 560), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    font = _load_font(72)
    rtl_kwargs = dict(direction="rtl", language="ur") if _has_raqm() else {}
    if not rtl_kwargs:
        logger.warning("Pillow without libraqm — Urdu shaping will look broken; rebuild pillow with raqm or use container fonts")

    lines = _rtl_wrap(caption, font, draw, WIDTH - 160) if rtl_kwargs else textwrap.wrap(caption, 22)
    line_h = 108
    box_h = line_h * len(lines) + 90
    y0 = (560 - box_h) // 2
    draw.rounded_rectangle([60, y0, WIDTH - 60, y0 + box_h], radius=40, fill=(0, 0, 0, 170))
    y = y0 + 45
    for line in lines:
        if rtl_kwargs:
            w = draw.textlength(line, font=font, **rtl_kwargs)
            draw.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=3, stroke_fill=(0, 0, 0, 220), **rtl_kwargs)
        else:
            w = draw.textlength(line, font=font)
            draw.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=3, stroke_fill=(0, 0, 0, 220))
        y += line_h
    return strip


def _pick_music() -> str | None:
    exact = os.environ.get("MUSIC_TRACK", "").strip()
    tracks = glob.glob("assets/music/*.mp3") + glob.glob("assets/music/*.wav")
    tracks = [t for t in tracks if "gitkeep" not in t and "ATTRIBUTION" not in t.upper()]
    if exact:
        match = [t for t in tracks if t.endswith(exact)]
        return match[0] if match else None
    return random.choice(tracks) if tracks else None


def build_video(image_paths: list, audio_segments: list, scenes: list) -> str:
    from moviepy.editor import (AudioFileClip, CompositeAudioClip, ImageClip,
                                concatenate_videoclips)

    clips = []
    for i, (img_path, seg) in enumerate(zip(image_paths, audio_segments)):
        duration = float(seg.get("duration", 4.0)) + 0.35  # small breath after each misra
        base = ImageClip(img_path).set_duration(duration)
        zoomed = base.resize(lambda t: 1 + (ZOOM - 1) * min(1.0, t / max(duration, 0.01))).set_position(("center", "center"))
        canvas = zoomed.on_color(size=(WIDTH, HEIGHT), color=(8, 8, 12), pos="center", col_opacity=1)

        caption_strip = _compose_caption_image(audio_segments[i].get("caption","" ) or scenes[i].get("caption", ""))
        tmp_strip = f"output/segments/caption_{i}.png"
        os.makedirs("output/segments", exist_ok=True)
        caption_strip.save(tmp_strip)
        from moviepy.editor import ImageClip as _IC
        caption_clip = (_IC(tmp_strip).set_duration(duration)
                        .set_position(("center", HEIGHT - 560 - 120)))
        from moviepy.editor import CompositeVideoClip
        clips.append(CompositeVideoClip([canvas, caption_clip], size=(WIDTH, HEIGHT)).set_duration(duration))

    video = concatenate_videoclips(clips, method="compose")

    audio_tracks = [AudioFileClip(seg["path"]) for seg in audio_segments]
    from moviepy.editor import concatenate_audioclips
    narration = concatenate_audioclips(audio_tracks).set_duration(video.duration)
    tracks = [narration]

    music_path = _pick_music()
    if music_path:
        music = AudioFileClip(music_path).volumex(MUSIC_VOLUME)
        if music.duration < video.duration:
            loops = int(np.ceil(video.duration / music.duration))
            from moviepy.editor import concatenate_audioclips as _cat
            music = _cat([music] * loops).subclip(0, video.duration)
        else:
            music = music.subclip(0, video.duration)
        tracks.append(music)
    video = video.set_audio(CompositeAudioClip(tracks))

    os.makedirs("output", exist_ok=True)
    out_path = "output/final_video.mp4"
    video.write_videofile(
        out_path, fps=FPS, codec="libx264", audio_codec="aac", bitrate="3500k",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-aspect", "9:16"],
        threads=max(1, (os.cpu_count() or 2) - 1), logger=None,
    )
    logger.info("Video written: %s (%.1fs)", out_path, video.duration)
    return out_path


def generate_thumbnail(first_image: str, title: str, category: str = "Poetry") -> str:
    img = Image.open(first_image).convert("RGB")
    img = img.resize((WIDTH, HEIGHT))
    strip = Image.new("RGBA", (WIDTH, 340), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    font = _load_font(96)
    rtl = dict(direction="rtl", language="ur") if _has_raqm() else {}
    lines = _rtl_wrap(title, font, draw, WIDTH - 140) if rtl else textwrap.wrap(title, 16)
    y = 40
    draw.rectangle([40, 20, WIDTH - 40, 20 + 130 * len(lines) + 60], fill=(0, 0, 0, 165))
    for line in lines:
        w = draw.textlength(line, font=font, **(rtl or {}))
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 235, 200, 255),
                  stroke_width=4, stroke_fill=(0, 0, 0, 230), **(rtl or {}))
        y += 130
    out = img.convert("RGBA")
    out.alpha_composite(strip, (0, HEIGHT - 340 - 160))
    os.makedirs("output", exist_ok=True)
    thumb_path = "output/thumbnail.jpg"
    out.convert("RGB").save(thumb_path, quality=90)
    logger.info("Thumbnail written: %s", thumb_path)
    return thumb_path
