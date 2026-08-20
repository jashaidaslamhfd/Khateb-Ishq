#!/usr/bin/env python3
"""One-off demo render: 3-scene Roman-Urdu captions, new cinematic motion
engine + free unique music. Run from repo root: python3 demo_render.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from image_generator import generate_scene_image
from voice_generator import generate_voice_segments
from music_generator import compose_unique_track
from video_editor import build_video

CAPTIONS = [
    "Dard bhi ek mehmaan hai, bulae bina aa jata hai.",
    "Raat chup hoti hai, magar dil ki awaaz nahin rukhti.",
    "Khamosh rehna bhi ek jawab hai, bas sunne wala chahiye.",
]
VISUAL_PROMPTS = [
    "Rainy night window view, empty room, single warm lamp, melancholic teal-orange moody cinematic mood, shallow depth of field, 4k atmospheric",
    "Lonely silhouette walking under streetlight in the fog, deep blue night tones, cinematic film grain, ultra wide shot, moody and quiet",
    "Morning light through curtains falling on an empty chair and a closed book, dust particles in the air, sad peaceful stillness, cinematic",
]
SCENES = [{"caption": c, "visual": v} for c, v in zip(CAPTIONS, VISUAL_PROMPTS)]


def main() -> str:
    os.makedirs("output", exist_ok=True)
    # 1) Images via the no-key Pollinations-flux provider
    hashes, fallbacks = set(), set()
    image_paths = []
    for i, scene in enumerate(SCENES):
        info = generate_scene_image(i, scene, hashes, fallbacks)
        path = info["path"] if isinstance(info, dict) else info
        assert os.path.exists(path), f"missing image for scene {i}"
        image_paths.append(path)
        print("image:", path, info.get("source") if isinstance(info, dict) else "")
    assert len(image_paths) == len(SCENES), "missing images"

    # 2) Voice
    audio_segments = generate_voice_segments(SCENES)
    for seg in audio_segments:
        print("audio:", seg["path"], round(seg["duration"], 1))

    # 3) Music
    total = sum(seg["duration"] for seg in audio_segments)
    music_path = compose_unique_track(theme="judai", target_duration=total + 4)
    print("music:", music_path)

    # 4) Build
    out = build_video(image_paths, audio_segments, SCENES, theme="judai")
    print("FINAL:", out)
    return out


if __name__ == "__main__":
    main()
