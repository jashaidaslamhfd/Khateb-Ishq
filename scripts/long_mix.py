#!/usr/bin/env python3
"""Weekly LONG-FORM 'poetry + background music' mix (8–15 min, 16:9 landscape).

WHY THIS EXISTS (views audit 2026-07): 87.9% of the channel's all-time views
come from the 'sad background music / dukhi status' SEARCH cluster — but raw
stock-music re-uploads get rejected by the YouTube Partner Program
('inauthentic/reused content', July 2025 policy).  This weekly long-form mix
rides the SAME search demand while staying monetization-safe, because every
second carries ORIGINAL narration (classical public-domain poets + original
couplets) layered over the channel's own royalty-free music beds.

Build pipeline (no moviepy — pure ffmpeg for speed on the runner):
  themes → scripts (Groq) → Urdu voice segments → graded stills →
  zoompan video blocks (ffmpeg) → concat → narration WAV + looped music bed →
  final 1280x720 MP4 → landscape thumbnail → upload via the same uploader
  (private → publishAt snaps to the next Pakistan-peak slot).

Env:
  MIX_POEMS   poems per mix (default 8 → ~8-12 min final video)
"""
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
os.chdir(REPO_ROOT)  # all relative asset paths behave like the daily pipeline

from theme_fetcher import get_theme                      # noqa: E402
from script_generator import generate_script             # noqa: E402
from image_generator import generate_scene_image         # noqa: E402
from voice_generator import generate_voice_segments      # noqa: E402
from video_editor import (                                # noqa: E402
    _FONT_CANDIDATES, _grade_image, _has_raqm, _load_font, _pick_music,
    _rtl_wrap,
)
from uploader import upload_all                          # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("long_mix")

POEMS = max(3, min(10, int(os.environ.get("MIX_POEMS", "8"))))
LEAD_IN = 2.5          # music-only intro seconds (first still fades the mood in)
GAP = 4.0              # music-only breather between poems
OUTRO = 14.0           # music-only tail (end-screen friendly)
W, H, FPS = 1280, 720, 24
HISTORY_PATH = Path(os.environ.get("VIDEO_HISTORY_PATH", "data/video_history.json"))
MAX_SCRIPT_ATTEMPTS = 3
MAX_IMAGE_RETRIES = 3
MUSIC_VOLUME = float(os.environ.get("MIX_MUSIC_VOLUME", os.environ.get("MUSIC_VOLUME", "0.08")))


# ----------------------------------------------------------------- helpers
def _run(cmd: list) -> None:
    logger.debug("RUN %s", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def _to_wav(src: Path, dst: Path) -> None:
    _run(["ffmpeg", "-y", "-i", src, "-ar", "44100", "-ac", "2", dst])


def _silence(duration: float, dst: Path) -> None:
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
          "-t", f"{duration:.3f}", dst])


def _concat_wavs(chunks: list, dst: Path) -> None:
    lst = dst.with_suffix(".list.txt")
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in chunks), encoding="utf-8")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
          "-c:a", "pcm_s16le", dst])


def _crop_landscape(img_path: Path, out_path: Path) -> None:
    from PIL import Image
    im = Image.open(img_path).convert("RGB")
    w, h = im.size
    target = W / H
    if w / h > target:   # too wide → crop sides
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    else:                # too tall → crop top/bottom
        nh = int(w / target)
        im = im.crop((0, (h - nh) // 2, w, (h + nh) // 2))
    im.resize((W * 2, H * 2), Image.LANCZOS).save(out_path, quality=92)


def _zoompan(img_path: Path, duration: float, out_path: Path, zoom_in: bool = True) -> None:
    frames = max(2, int(duration * FPS))
    zexpr = "min(zoom+0.00045,1.18)" if zoom_in else "max(zoom-0.00045,1.0)"
    vf = (f"scale={W*2}:{H*2},zoompan=z='{zexpr}':d={frames}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
          "setsar=1,format=yuv420p")
    _run(["ffmpeg", "-y", "-loop", "1", "-t", f"{duration + 0.5:.2f}", "-i",
          img_path, "-vf", vf, "-t", f"{duration:.2f}", "-an",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", out_path])


# ----------------------------------------------------------------- poems
def _fresh_script(topic: str) -> dict:
    for attempt in range(1, MAX_SCRIPT_ATTEMPTS + 1):
        try:
            return generate_script(topic)
        except Exception as exc:  # noqa: BLE001
            logger.warning("script attempt %d failed: %s", attempt, exc)
            time.sleep(20 * attempt)
    raise RuntimeError("script generation failed after retries")


def _poem_images(script: dict, poem_idx: int, used_hashes: set, used_fallbacks: set) -> list:
    """Two landscape-graded stills per poem; placeholder keeps the mix alive
    if every provider hiccups for one scene."""
    from PIL import Image  # deferred: only needed here
    paths = []
    work = Path(f"output/mix/img/p{poem_idx:02d}")
    work.mkdir(parents=True, exist_ok=True)
    for j in range(2):
        scene = script["scenes"][j % len(script["scenes"])]
        got = None
        for _ in range(MAX_IMAGE_RETRIES):
            try:
                res = generate_scene_image(j, scene, used_hashes, used_fallbacks)
            except Exception as exc:  # noqa: BLE001
                logger.warning("image provider error: %s", exc)
                res = None
            if res and os.path.exists(res.get("path", "")):
                got = res["path"]
                break
            time.sleep(5)
        raw = got or "assets/placeholder.png"
        graded = work / f"scene{j}.jpg"
        _grade_image(raw, str(graded), variant=j)
        land = work / f"scene{j}_land.jpg"
        _crop_landscape(graded, land)
        paths.append(land)
    return paths


def _build_poem(idx: int) -> dict:
    theme_rec = get_theme()
    topic = theme_rec["topic"]
    logger.info("=== POEM %d/%d — %s", idx, POEMS, topic)
    script = _fresh_script(topic)

    vdir = Path(f"output/mix/voice/p{idx:02d}")
    segments = generate_voice_segments(script["scenes"], output_dir=str(vdir))
    wavs = []
    for k, seg in enumerate(segments):
        w = vdir / f"seg{k}.wav"
        _to_wav(Path(seg["path"]), w)
        wavs.append(w)
    voice_wav = vdir / "poem.wav"
    _concat_wavs(wavs, voice_wav)

    used_hashes, used_fallbacks = set(), set()
    images = _poem_images(script, idx, used_hashes, used_fallbacks)
    return {
        "topic": topic,
        "title": script.get("title") or "اردو شاعری",
        "poet": script.get("poet") or "Original",
        "voiceover": script.get("voiceover", "")[:300],
        "voice_wav": voice_wav,
        "images": images,
    }


# ----------------------------------------------------------------- assembly
def _assemble(poems: list) -> tuple:
    """Returns (final_mp4, chapters[list of (sec,label)], total_duration)."""
    work = Path("output/mix/assemble")
    work.mkdir(parents=True, exist_ok=True)

    # ---- narration master (chapters tracked from the same clock) ----
    chunks, chapters = [], []
    s = work / "sil_lead.wav"
    _silence(LEAD_IN, s)
    chunks.append(s)
    clock = LEAD_IN
    for i, p in enumerate(poems):
        chapters.append((clock, f"{p['title']}  —  {p['poet'].split(' (')[0]}"))
        dur = _ffprobe_duration(p["voice_wav"])
        chunks.append(p["voice_wav"])
        clock += dur
        s = work / f"sil_gap{i}.wav"
        _silence(GAP, s)
        chunks.append(s)
        clock += GAP
    s = work / "sil_outro.wav"
    _silence(OUTRO, s)
    chunks.append(s)
    clock += OUTRO
    narration = work / "narration.wav"
    _concat_wavs(chunks, narration)
    total = _ffprobe_duration(narration)
    logger.info("Narration master: %.1fs (target %.1fs)", total, clock)

    # ---- silent video: intro + per-poem two-still zoompan + outro ----
    blocks = []
    first_still = poems[0]["images"][0]
    intro = work / "blk_intro.mp4"
    _zoompan(first_still, LEAD_IN, intro)
    blocks.append(intro)
    for i, p in enumerate(poems):
        dur = _ffprobe_duration(p["voice_wav"]) + GAP
        half = round(dur / 2, 2)
        for j, (img, seg_d) in enumerate(((p["images"][0], half), (p["images"][1], dur - half))):
            blk = work / f"blk_p{i:02d}_{j}.mp4"
            _zoompan(img, max(1.0, seg_d), blk, zoom_in=((i + j) % 2 == 0))
            blocks.append(blk)
    outro = work / "blk_outro.mp4"
    _zoompan(poems[-1]["images"][1], OUTRO, outro, zoom_in=False)
    blocks.append(outro)

    lst = work / "video.list.txt"
    lst.write_text("".join(f"file '{b.resolve()}'\n" for b in blocks), encoding="utf-8")
    silent = work / "silent.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
          "-an", "-c:v", "copy", silent])

    # ---- mux: video + narration + looped music bed ----
    music = _pick_music()
    final = work / "final.mp4"
    if music:
        logger.info("Music bed: %s (vol %.2f)", music, MUSIC_VOLUME)
        _run(["ffmpeg", "-y", "-i", silent, "-i", narration,
              "-stream_loop", "-1", "-i", music,
              "-filter_complex",
              f"[2:a]volume={MUSIC_VOLUME}[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    else:  # never ship silent poetry just because a file went missing
        _run(["ffmpeg", "-y", "-i", silent, "-i", narration,
              "-map", "0:v", "-map", "1:a", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "192k", final])
    return final, chapters, total


# ----------------------------------------------------------------- thumbnail
def _mix_thumbnail(still: Path, urdu_line: str, mix_no: int) -> str:
    from PIL import Image, ImageDraw
    img = Image.open(still).convert("RGBA").resize((W, H))
    strip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    d.rectangle([0, H - 300, W, H], fill=(0, 0, 0, 190))
    out = Image.alpha_composite(img, strip)
    draw = ImageDraw.Draw(out)

    font_latin = None
    try:
        from video_editor import _load_latin_font
        font_latin = _load_latin_font(54)
    except Exception:  # noqa: BLE001
        pass
    if font_latin:
        draw.text((70, H - 290), "BACKGROUND MUSIC + POETRY MIX",
                  font=font_latin, fill=(235, 200, 120), stroke_width=2,
                  stroke_fill=(0, 0, 0))

    font = _load_font(88)
    rtl = dict(direction="rtl", language="ur") if _has_raqm() else {}
    lines = _rtl_wrap(urdu_line, font, draw, W - 160) if rtl else [urdu_line]
    y = H - 215
    for line in lines[:2]:
        draw.text((70, y), line, font=font, fill=(255, 240, 210),
                  stroke_width=4, stroke_fill=(0, 0, 0), **(rtl or {}))
        y += 105
    path = "output/mix/thumbnail.jpg"
    out.convert("RGB").save(path, quality=92)
    logger.info("Thumbnail: %s", path)
    return path


# ----------------------------------------------------------------- main
def main() -> int:
    random.seed()
    t0 = time.time()
    poems = []
    for i in range(1, POEMS + 1):
        try:
            poems.append(_build_poem(i))
        except Exception as exc:  # noqa: BLE001
            logger.error("poem %d failed completely: %s — skipping it", i, exc)
        if len(poems) >= 5 and len(poems) == POEMS - 1:
            break
    if len(poems) < 3:
        logger.error("Only %d poems built — aborting mix.", len(poems))
        return 1

    final, chapters, total = _assemble(poems)

    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8")) if HISTORY_PATH.exists() else []
    mix_no = 1 + sum(1 for h in history if h.get("trend_source") == "long_mix")
    urdu_title = f"اداسی کی راتیں — کلام میックス #{mix_no}"
    title = (f"{urdu_title} 💔 | sad urdu poetry + background music | "
             f"dukhi status mix")[:100]

    def _mmss(sec: float) -> str:
        m, s_ = divmod(int(sec), 60)
        return f"{m:02d}:{s_:02d}"

    chapter_lines = "\n".join(f"{_mmss(s)}  {label}" for s, label in chapters)
    description = (
        "Sad Urdu poetry long mix — classical Kalam (Ghalib · Iqbal · Mir · "
        "Bulleh Shah · Waris Shah) + original 2-line shayari over a soft sad "
        "background music bed. Dukhi status ke liye perfect. 🌙\n\n"
        f"{chapter_lines}\n\n"
        "Rozana nayi shayari ke liye channel follow karein.\n"
        "#sadpoetry #urdupoetry #backgroundmusic #dukhistatus #shayari #2linepoetry"
    )
    tags = ["sad urdu poetry", "background music for poetry", "dukhi status",
            "sad poetry background music", "urdu poetry mix", "long poetry video",
            "heart touching poetry", "2 line sad poetry", "urdu shayari",
            "sad shayari status", "ghalib poetry", "iqbal poetry"]

    thumb = _mix_thumbnail(poems[0]["images"][0], urdu_title, mix_no)
    script_data = {
        "title": title,                 # already bilingual (pipes) → uploader passes through
        "description": description,
        "tags": tags,
        "poet": "",
    }
    result = upload_all(str(final), thumb, script_data)
    logger.info("Upload result: %s", json.dumps(result)[:400])

    ok = bool(result.get("youtube_success") or result.get("youtube_video_id"))
    entry = {
        "title": title, "topic": f"long_mix #{mix_no} ({len(poems)} poems)",
        "poet": "Mix (classics + original)", "source": "long_mix",
        "trend_source": "long_mix",
        "voiceover": description[:400],
        "duration_seconds": round(total, 1),
        "posted_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat() if ok else None,
        "youtube_video_id": result.get("youtube_video_id"),
    }
    history.append(entry)
    for p in poems:   # mark each poem's theme as used so the daily pipeline never repeats it
        history.append({"title": p["title"], "topic": p["topic"], "poet": p["poet"],
                        "source": "long_mix_poem", "trend_source": "long_mix_poem",
                        "voiceover": p["voiceover"], "posted_at": entry["posted_at"],
                        "youtube_video_id": entry["youtube_video_id"]})
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("DONE in %.0fs — mix #%d, %.1f min, %d poems",
                time.time() - t0, mix_no, total / 60, len(poems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
