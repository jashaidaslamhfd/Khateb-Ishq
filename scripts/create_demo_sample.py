#!/usr/bin/env python3
"""
Khateb-Ishq — Demo Audio Sample Creator.

Generates a master studio demo combining:
  1. Soul-stirring Jaun Elia style Urdu couplet
  2. Studio-mastered warm baritone voice with Mushaira pauses
  3. Viral TikTok/YouTube multi-instrument sad track (Flute + Violins + Drums + Piano)
"""

import asyncio
import os
import subprocess
import edge_tts
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

URDU_LINES = [
    "کبھی کبھی دل یہ سوچ کر بھی اداس ہو جاتا ہے...",
    "کہ جنہیں ہم نے ٹوٹ کر چاہا...",
    "وہ بھی کسی اور کے ہو گئے...",
    "ہم نے تو خود کو بھی تیری خاطر چھوڑ دیا تھا...",
    "اور تم نے ہمیں... زمانے کے لیے چھوڑ دیا۔"
]


async def generate_demo():
    os.makedirs("/home/user/Khateb-Ishq/output", exist_ok=True)
    raw_mp3 = "/home/user/Khateb-Ishq/output/raw_voice.mp3"
    master_wav = "/home/user/Khateb-Ishq/output/master_voice.wav"
    final_mp3 = "/home/user/Khateb-Ishq/output/demo_sad_poetry_mushaira.mp3"
    bg_music = "/home/user/Khateb-Ishq/assets/music/viral_tiktok_sad_flute_violin_beat.wav"

    text = "\n\n".join(URDU_LINES)
    print("🎙️ Synthesizing Urdu voiceover with Mushaira pauses...")
    comm = edge_tts.Communicate(text, "ur-PK-AsadNeural", rate="-14%")
    await comm.save(raw_mp3)

    print("🎛️ Applying studio warm baritone EQ & room acoustic mastering...")
    # Studio vocal mastering
    cmd_vocal = [
        FFMPEG, "-y", "-i", raw_mp3,
        "-af", "equalizer=f=220:t=q:w=1.2:g=3.5,equalizer=f=3800:t=q:w=2.0:g=1.5,aecho=0.8:0.88:35|70:0.12|0.08,loudnorm=I=-14:TP=-1.5:LRA=10",
        "-ar", "44100", "-ac", "2", master_wav
    ]
    subprocess.run(cmd_vocal, check=True)

    # Get vocal duration
    r = subprocess.run([FFMPEG, "-i", master_wav], capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if m:
        h, mins, s = m.groups()
        dur = int(h) * 3600 + int(mins) * 60 + float(s) + 2.5
    else:
        dur = 25.0

    print(f"🎵 Mixing with Multi-Instrument Viral Sad Bed (Flute + Violins + Drums + Piano) — Duration: {dur:.1f}s...")
    cmd_mix = [
        FFMPEG, "-y",
        "-i", master_wav,
        "-i", bg_music,
        "-filter_complex", f"[1:a]volume=0.22,afade=t=in:ss=0:d=1.0,afade=t=out:st={dur-2.5}:d=2.5[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "256k",
        "-t", str(dur),
        final_mp3
    ]
    subprocess.run(cmd_mix, check=True)
    print(f"🎉 MASTER DEMO GENERATED: {final_mp3}")
    return final_mp3


if __name__ == "__main__":
    asyncio.run(generate_demo())
