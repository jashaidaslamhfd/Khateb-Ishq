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

# ---- Viral-status look (owner request 2026-07-22) ------------------------
# CAPTION_SCRIPT=roman -> on-screen captions in Roman Urdu (Latin); the VOICE
# always stays native Urdu (scene["caption"]). "urdu" reverts to Nastaliq text.
CAPTION_SCRIPT = os.environ.get("CAPTION_SCRIPT", "roman").strip().lower()
# FAST_CUT=1 -> each scene becomes two punch-cuts (alt pan/zoom) like trending
# sad-status edits. APPLY_GRADE=1 -> warm contrast grade + vignette + grain.
FAST_CUT = os.environ.get("FAST_CUT", "1").strip().lower() in ("1", "true", "yes")
APPLY_GRADE = os.environ.get("APPLY_GRADE", "1").strip().lower() in ("1", "true", "yes")

_LATIN_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "assets/fonts/DejaVuSans-Bold.ttf",
]


def _load_latin_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _LATIN_FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    logger.warning("No Latin font found — Pillow default bitmap font (small)")
    return ImageFont.load_default()


def _pick_display_caption(scene: dict, seg: dict) -> str:
    """Screen text: Roman Urdu when configured and the script provided one —
    else the Urdu caption. Voice text is NEVER touched by this choice."""
    if CAPTION_SCRIPT == "roman":
        roman = (scene.get("caption_roman") or "").strip()
        if roman:
            return roman
    return (seg.get("caption") or scene.get("caption") or "").strip()


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


_FX_CACHE: dict = {}


def _vignette() -> np.ndarray:
    """Radial dark-edge mask, cached (2M-pixel grid is not cheap)."""
    if "vig" not in _FX_CACHE:
        yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
        d = np.sqrt(((xx - WIDTH / 2) / (WIDTH / 2)) ** 2 + ((yy - HEIGHT / 2) / (HEIGHT / 2)) ** 2)
        _FX_CACHE["vig"] = (1.0 - 0.45 * np.clip(d - 0.55, 0, 1) ** 1.5).astype(np.float32)
    return _FX_CACHE["vig"]


def _grain() -> np.ndarray:
    if "grain" not in _FX_CACHE:
        rng = np.random.default_rng(7)
        _FX_CACHE["grain"] = rng.normal(0.0, 4.0, (HEIGHT, WIDTH)).astype(np.float32)
    return _FX_CACHE["grain"]


def _grade_image(in_path: str, out_path: str, variant: int = 0) -> str:
    """Cover-crop to 1080x1920 (alternate pans for fast-cut halves), then apply
    the moody warm grade + vignette + film grain — the sad-status look."""
    img = Image.open(in_path).convert("RGB")
    sw, sh = img.size
    scale = max(WIDTH / sw, HEIGHT / sh)
    img = img.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    nw, nh = img.size
    span = max(0, nw - WIDTH)
    x0 = int(span * (0.5 if variant == 0 else (0.12 if variant % 2 else 0.88)))
    y0 = max(0, (nh - HEIGHT) // 2)
    img = img.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT))
    arr = np.asarray(img).astype(np.float32)
    arr[..., 0] *= 1.06              # warm highlights
    arr[..., 2] *= 0.94              # cool shadows
    arr = (arr - 128.0) * 1.08 + 118.0
    arr *= _vignette()[..., None]
    arr += _grain()[..., None]
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(out_path, quality=88)
    return out_path


def _scene_visual_files(img_path: str, index: int) -> list:
    """Files for this scene's video: 2 graded alt-crops in fast-cut mode,
    1 graded crop if only grading, untouched original if neither."""
    if not APPLY_GRADE and not FAST_CUT:
        return [img_path]
    os.makedirs("output/segments", exist_ok=True)
    if FAST_CUT:
        a = _grade_image(img_path, f"output/segments/fx_{index}_a.jpg", variant=0)
        b = _grade_image(img_path, f"output/segments/fx_{index}_b.jpg", variant=1)
        return [a, b]
    return [_grade_image(img_path, f"output/segments/fx_{index}.jpg", variant=0)]


def _compose_caption_image(caption: str) -> Image.Image:
    """Transparent caption strip (1080x560). Two render branches:
    - Latin text (Roman Urdu): DejaVu bold, LTR, textwrap.
    - Urdu text: Naskh + libraqm RTL shaping with dark scrim."""
    strip = Image.new("RGBA", (WIDTH, 560), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    is_latin = caption and not any("\u0600" <= ch <= "\u06FF" for ch in caption)

    if is_latin:
        # ---- Roman Urdu branch: no raqm needed, LTR DejaVu ----
        font = _load_latin_font(60)
        lines = textwrap.wrap(caption, 22)
        line_h = 78
        box_h = line_h * len(lines) + 74
        y0 = (560 - box_h) // 2
        draw.rounded_rectangle([50, y0, WIDTH - 50, y0 + box_h], radius=34, fill=(0, 0, 0, 168))
        y = y0 + 37
        for line in lines:
            w = draw.textlength(line, font=font)
            draw.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 246, 230, 255),
                      stroke_width=3, stroke_fill=(0, 0, 0, 225))
            y += line_h
        return strip

    # ---- Urdu (Nastaliq) branch: raqm RTL shaping ----
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
        files = _scene_visual_files(img_path, i)           # graded crops (1 or 2)
        per = duration / len(files)
        cuts = []
        for j, f in enumerate(files):
            base = ImageClip(f).set_duration(per)
            start_zoom = 1.0 + (ZOOM - 1.0) * (j / max(len(files) - 1, 1)) * 0.6
            zoomed = base.resize(
                lambda t, z0=start_zoom: z0 + ((ZOOM - 1.0) - (z0 - 1.0)) * min(1.0, t / max(per, 0.01))
            ).set_position(("center", "center"))
            cuts.append(zoomed.on_color(size=(WIDTH, HEIGHT), color=(8, 8, 12), pos="center", col_opacity=1))
        canvas = (concatenate_videoclips(cuts, method="compose") if len(cuts) > 1 else cuts[0])
        canvas = canvas.set_duration(duration)

        caption_strip = _compose_caption_image(_pick_display_caption(scenes[i], seg))
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
