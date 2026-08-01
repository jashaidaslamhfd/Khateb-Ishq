#!/usr/bin/env python3
"""VIRAL Background Music Generator — The kind people ACTUALLY USE in their videos.

Problem with old music: Technical, orchestral, cinematic — but BORING.
Nobody puts a "cinematic orchestral piece" behind their TikTok shayari.

What goes VIRAL as background music on TikTok/Reels/Shorts:
  1. Simple piano melody + heavy rain (the #1 viral combo)
  2. Slow sad melody that gets stuck in your head
  3. A gentle desi beat (tabla/dholak) that gives rhythm
  4. The "feel" of: "I want THIS behind my poetry video"
  5. Loopable — plays seamlessly on repeat

This generator creates music that people WANT to use, not just hear.

Output: 5 tracks, each 2 minutes (long enough for TikTok/Reels)
  1. barish_piano_viral — Rain + Simple Piano + Gentle Tabla (THE viral one)
  2. raat_ka_dard — Night Violin + Soft Rain + Tabla (deep sad)
  3. judai_ka_mausam — Slow Piano + Rain + Dholak (heartbreak feel)
  4. tanhai_ka_safar — Empty Piano + Distant Rain + Minimal Tabla (lonely)
  5. dukh_ka_dariya — Deep Piano + Rain + Tabla (the one that makes you cry)

Usage: python scripts/generate_viral_music.py
"""

import os
import wave
import numpy as np

SR = 22050
DUR = 120.0  # 2 minutes — long enough for TikTok/Reels
OUT_DIR = os.path.join("assets", "music")


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _fade_env(n, attack_s, release_s):
    env = np.ones(n)
    a = min(int(SR * attack_s), n // 2)
    r = min(int(SR * release_s), n // 2)
    if a > 0:
        env[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 0:
        env[-r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return env


# ═══════════════════════════════════════════════════════════════
# SIMPLE PIANO — The viral kind (not complex, EASY to listen to)
# ═══════════════════════════════════════════════════════════════

def piano_note(midi, dur, vel=1.0):
    """Simple, emotional piano — like the viral TikTok sad piano tracks.
    Key: NOT too many harmonics. Clean, warm, simple. That's what makes
    people want to use it — it doesn't compete with their voice."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    # Simple: fundamental + soft 2nd harmonic only
    sig = (np.sin(2 * np.pi * f * t) +
           0.3 * np.sin(2 * np.pi * 2 * f * t) +
           0.08 * np.sin(2 * np.pi * 3 * f * t))
    # Soft attack, long decay (the "sad" feel)
    attack = max(2, int(SR * 0.008))
    env = np.exp(-t / (dur * 0.45))  # Slow decay = emotional
    env[:attack] = np.linspace(0, 1, attack)
    return (sig * env * vel).astype(np.float64) / 2.0


def violin_note(midi, dur, vel=1.0):
    """Simple emotional violin — not complex, just SAD.
    Viral violin tracks are SIMPLE — just a few notes, lots of feeling."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    # Gentle vibrato (slow, emotional)
    vibrato = 1.0 + 0.006 * np.sin(2 * np.pi * 5.0 * t)
    phase = 2 * np.pi * f * np.cumsum(vibrato) / SR
    sig = (np.sin(phase) +
           0.35 * np.sin(2 * phase) +
           0.1 * np.sin(3 * phase))
    # Slow bow attack
    bow_attack = min(int(SR * 0.05), n)
    if bow_attack > 0:
        sig[:bow_attack] *= np.linspace(0, 1, bow_attack) ** 0.5
    env = np.exp(-t / (dur * 1.0))
    return (sig * env * vel).astype(np.float64) / 1.6


# ═══════════════════════════════════════════════════════════════
# DESI TABLA / DHOLAK — The SECRET ingredient
# ═══════════════════════════════════════════════════════════════
# Why viral BG music works on TikTok: it has a GENTLE BEAT.
# Pure piano/rain is too flat. Adding a soft tabla gives RHYTHM
# that makes people want to lip-sync or recite over it.

def tabla_hit(n, position, gain=0.15):
    """Single tabla/dholak hit — soft, not aggressive."""
    length = int(SR * 0.15)  # 150ms hit
    if position + length > n:
        return np.zeros(n)
    t = np.arange(length) / SR
    # Low "dum" sound
    freq = 80 + 40 * np.exp(-t * 20)  # Pitch drops quickly
    hit = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 15)
    # Add a click
    click = np.exp(-t * 80) * 0.3
    out = np.zeros(n)
    combined = (hit + click) * gain
    out[position:min(position + length, n)] = combined[:min(length, n - position)]
    return out


def dholak_pattern(n, bpm=60, gain=0.08):
    """Generate a full dholak pattern for the entire track.
    Pattern: DUM . . ka . . DUM . . ka . (4/4 time, slow)
    This is the BASIC pattern that makes people want to recite over it."""
    beat_s = 60.0 / bpm
    out = np.zeros(n)
    t = 0
    while t < n / SR:
        pos = int(t * SR)
        if pos >= n:
            break
        # DUM (strong beat)
        out += tabla_hit(n, pos, gain)
        # KA (weak beat, half beat later)
        ka_pos = int((t + beat_s * 0.5) * SR)
        if ka_pos < n:
            out += tabla_hit(n, ka_pos, gain * 0.5)
        t += beat_s
    return out


# ═══════════════════════════════════════════════════════════════
# RAIN — The #1 viral element (heavy, consistent, warm)
# ═══════════════════════════════════════════════════════════════

def rain_layer(n, gain=0.04, intensity=1.0):
    """HEAVY rain — this is what makes the track VIRAL.
    The rain + piano combo is the #1 most used background on TikTok.
    It should be LOUD enough to hear but not cover the melody."""
    rng = np.random.default_rng(42)
    noise = rng.standard_normal((2, n))
    # Low-pass filter (warm, not harsh)
    k = np.hanning(401)
    k /= k.sum()
    out_l = np.convolve(noise[0], k, mode="same")
    out_r = np.convolve(noise[1], k, mode="same")
    # Slow amplitude modulation (rain intensity varies naturally)
    mod = np.convolve(rng.standard_normal(n), np.hanning(int(SR * 2)), mode="same")
    mod /= np.abs(mod).max() + 1e-9
    lfo = 0.6 + 0.4 * mod
    return np.stack([out_l * lfo, out_r * lfo]) * gain * intensity * 5.0


# ═══════════════════════════════════════════════════════════════
# SIMPLE REVERB — Depth without complexity
# ═══════════════════════════════════════════════════════════════

def simple_reverb(sig, wet=0.25):
    """Simple multi-tap delay reverb."""
    out = sig.copy()
    is_stereo = sig.ndim == 2
    for delay_ms in [23, 37, 53, 71, 89, 113]:
        offset = int(SR * delay_ms / 1000.0)
        g = wet * (0.4 ** (delay_ms / 30.0))
        if is_stereo:
            if offset < sig.shape[1]:
                out[:, offset:] += sig[:, :-offset] * g
        else:
            if offset < len(sig):
                out[offset:] += sig[:-offset] * g
    return out


# ═══════════════════════════════════════════════════════════════
# MELODY GENERATOR — SIMPLE, MEMORABLE, STICKS IN YOUR HEAD
# ═══════════════════════════════════════════════════════════════
# The key to viral music: SIMPLICITY. The melody should be so simple
# that you can hum it after hearing it once. No complex patterns.

def generate_simple_melody(scale, root, bpm, total_bars, intro_s, seed):
    """Generate a SIMPLE, MEMORABLE melody that gets stuck in your head.
    
    Viral music rule: 3-4 notes max per phrase. Repeat. That's it.
    Think of the viral TikTok sad piano — it's always 3-4 notes."""
    rng = np.random.RandomState(seed)
    spb = 60.0 / bpm
    bar_s = 4 * spb
    notes = []

    # Pick 3-4 notes from the scale (the "hook" notes)
    hook_notes = [scale[len(scale) // 2 + i] for i in [-1, 0, 1, 2]]
    
    for bar in range(total_bars):
        is_last = bar >= total_bars - 2
        if is_last:
            # Resolve to root (octave up for emotional impact)
            notes.append((intro_s + bar * bar_s, 4.0 * spb, root + 12, 0.7))
            continue

        # Simple pattern: 2 notes per bar, long and slow
        for beat in [0, 2]:
            t0 = intro_s + bar * bar_s + beat * spb
            dur = 2.0 * spb  # Long notes = emotional
            midi = rng.choice(hook_notes)
            vel = 0.5 + 0.2 * rng.random()
            if beat == 0:
                vel += 0.1  # Emphasize first beat
            notes.append((t0, dur, midi, vel))

    return notes


def generate_violin_melody(scale, root, bpm, total_bars, intro_s, seed):
    """Generate a SIMPLE violin melody — the emotional counter-melody.
    Plays LONG notes that support the piano, not compete with it."""
    rng = np.random.RandomState(seed + 500)
    spb = 60.0 / bpm
    bar_s = 4 * spb
    notes = []
    
    # Violin plays every 2-4 bars (not every bar — it's a counter-melody)
    t = intro_s + 4.0
    while t < intro_s + total_bars * bar_s - 8.0:
        dur = rng.uniform(3.0, 5.0)
        midi = rng.choice([root - 12, root - 7, root - 5, root, root + 5])
        vel = 0.3 + 0.15 * rng.random()
        notes.append((t, dur, midi, vel))
        t += rng.uniform(4.0, 8.0)
    
    return notes


# ═══════════════════════════════════════════════════════════════
# PAD CHORD — Simple, warm, doesn't compete
# ═══════════════════════════════════════════════════════════════

def pad_chord(midis, dur, gain=0.5):
    """Simple warm pad — NOT complex. Just fills the space."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    left, right = np.zeros(n), np.zeros(n)
    for m in midis:
        f = hz(m)
        # Detuned for width
        left += np.sin(2 * np.pi * f * 0.999 * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)
        right += np.sin(2 * np.pi * f * 1.001 * t) + 0.2 * np.sin(2 * np.pi * 2.001 * f * t)
    env = _fade_env(n, min(1.5, dur * 0.3), min(1.5, dur * 0.4))
    return np.stack([left * env, right * env]) * gain / (1.2 * len(midis))


# ═══════════════════════════════════════════════════════════════
# CHORD PROGRESSIONS — Simple, emotional, Desi
# ═══════════════════════════════════════════════════════════════

# A minor (the saddest key)
Am = [57, 60, 64]
F  = [53, 57, 60]
C  = [48, 52, 55]
G  = [55, 59, 62]
Em = [52, 55, 59]
Dm = [50, 53, 57]
Bb = [46, 50, 53]
Gm = [55, 58, 62]

# Pentatonic scales
AM_PENT = [57, 60, 62, 64, 67, 69, 72, 74, 77]
EM_PENT = [52, 55, 57, 59, 62, 64, 67, 69, 71]
DM_PENT = [50, 53, 55, 57, 60, 62, 65, 67, 69]
GM_PENT = [55, 58, 60, 62, 65, 67, 70, 72, 74]


# ═══════════════════════════════════════════════════════════════
# TRACK BUILDERS — Each one is a UNIQUE viral composition
# ═══════════════════════════════════════════════════════════════

def _place_notes(notes, total_n, voice_fn):
    left, right = np.zeros(total_n), np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = voice_fn(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n - idx)
        if L > 0:
            left[idx:idx+L] += sig[:L] * 0.55
            right[idx:idx+L] += sig[:L] * 0.45
    return np.stack([left, right])


def _progression(chords, chord_s, vol):
    n = int(SR * DUR)
    out = np.zeros((2, n))
    start = 0.0
    for ch in chords:
        seg = pad_chord(ch, chord_s + 2.0, gain=vol)
        idx = int(start * SR)
        L = min(seg.shape[1], n - idx)
        if L > 0:
            out[:, idx:idx+L] += seg[:, :L]
        start += chord_s
        if start >= DUR:
            break
    return out


def _dynamic_swell(n, depth=0.2):
    t = np.arange(n) / SR
    total_s = n / SR
    return 1.0 + depth * (
        0.5 * np.sin(2 * np.pi * t / total_s - np.pi/2) +
        0.3 * np.sin(2 * np.pi * t / total_s * 2 - np.pi/2) +
        0.2 * np.sin(2 * np.pi * t / total_s * 0.5 - np.pi/2)
    )


def master(sig, name):
    sig = np.tanh(sig * 1.0)
    f = int(SR * 3.0)
    if sig.ndim == 2:
        sig[0, :f] *= np.linspace(0, 1, f)
        sig[0, -f:] *= np.linspace(1, 0, f)
        sig[1, :f] *= np.linspace(0, 1, f)
        sig[1, -f:] *= np.linspace(1, 0, f)
    peak = np.abs(sig).max() or 1.0
    pcm = (sig / peak * 0.70 * 32767).astype(np.int16)
    if pcm.ndim == 2:
        pcm = pcm.T
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  ✅ {name} ({DUR:.0f}s, {os.path.getsize(path)//1024}KB) — USE THIS as background music!")
    return path


# ═══════════════════════════════════════════════════════════════
# TRACK 1: 🌧️ Barish + Piano + Tabla — THE VIRAL ONE
# This is the #1 most viral background music type on TikTok.
# Simple piano + heavy rain + gentle tabla. People USE this.
# ═══════════════════════════════════════════════════════════════

def build_barish_piano_viral():
    np.random.seed(101)
    n = int(SR * DUR)
    bpm = 56
    root = 57  # A minor
    intro_s = 4.0

    # Simple pad progression (Am - F - C - G) — the most common sad progression
    pads = _progression([Am, F, C, G], chord_s=12.0, vol=0.6)

    # Simple piano melody (3-4 notes, repeating)
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_simple_melody(AM_PENT, root, bpm, total_bars, intro_s, seed=101)
    piano = _place_notes(melody, n, piano_note)

    # Rain — HEAVY (this is the viral element)
    rain = rain_layer(n, gain=0.045, intensity=1.3)

    # Tabla — gentle, not aggressive
    tabla = dholak_pattern(n, bpm=bpm, gain=0.06)

    # Dynamic swell
    swell = _dynamic_swell(n, depth=0.2)

    # Mix — piano + rain + tabla = VIRAL
    mix = pads + piano * 1.8 + rain + tabla * 0.5
    mix[0] *= swell
    mix[1] *= swell

    # Reverb for depth
    mix = simple_reverb(mix, wet=0.3)

    return master(mix, "barish_piano_viral.wav")


# ═══════════════════════════════════════════════════════════════
# TRACK 2: 🌙 Raat ka Dard — Violin + Rain + Tabla
# Deep sad violin with rain. For the "raat mein tanhai" feel.
# ═══════════════════════════════════════════════════════════════

def build_raat_ka_dard():
    np.random.seed(202)
    n = int(SR * DUR)
    bpm = 52
    root = 52  # E minor
    intro_s = 5.0

    pads = _progression([Em, C, G, Am], chord_s=14.0, vol=0.5)

    # Violin melody — long, emotional notes
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_simple_melody(EM_PENT, root, bpm, total_bars, intro_s, seed=202)
    violin_melody = generate_violin_melody(EM_PENT, root, bpm, total_bars, intro_s, seed=202)
    piano = _place_notes(melody, n, piano_note)
    violin = _place_notes(violin_melody, n, violin_note)

    # Rain + tabla
    rain = rain_layer(n, gain=0.035, intensity=1.0)
    tabla = dholak_pattern(n, bpm=bpm, gain=0.05)

    swell = _dynamic_swell(n, depth=0.25)

    mix = pads + piano * 1.5 + violin * 1.8 + rain + tabla * 0.4
    mix[0] *= swell
    mix[1] *= swell
    mix = simple_reverb(mix, wet=0.35)

    return master(mix, "raat_ka_dard.wav")


# ═══════════════════════════════════════════════════════════════
# TRACK 3: 💔 Judai ka Mausam — Slow Piano + Rain + Dholak
# Heartbreak feel. The kind that plays in your head after a breakup.
# ═══════════════════════════════════════════════════════════════

def build_judai_ka_mausam():
    np.random.seed(303)
    n = int(SR * DUR)
    bpm = 50
    root = 50  # D minor
    intro_s = 5.0

    pads = _progression([Dm, Bb, F, C], chord_s=14.0, vol=0.5)

    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_simple_melody(DM_PENT, root, bpm, total_bars, intro_s, seed=303)
    piano = _place_notes(melody, n, piano_note)

    rain = rain_layer(n, gain=0.04, intensity=1.1)
    tabla = dholak_pattern(n, bpm=bpm, gain=0.07)

    swell = _dynamic_swell(n, depth=0.3)

    mix = pads + piano * 2.0 + rain + tabla * 0.5
    mix[0] *= swell
    mix[1] *= swell
    mix = simple_reverb(mix, wet=0.3)

    return master(mix, "judai_ka_mausam.wav")


# ═══════════════════════════════════════════════════════════════
# TRACK 4: 🏜️ Tanhai ka Safar — Empty Piano + Distant Rain + Minimal Tabla
# Lonely, empty feel. Like walking alone at night.
# ═══════════════════════════════════════════════════════════════

def build_tanhai_ka_safar():
    np.random.seed(404)
    n = int(SR * DUR)
    bpm = 48
    root = 57  # A minor
    intro_s = 6.0

    # Very sparse pads
    pads = _progression([Am, F, C, Em], chord_s=16.0, vol=0.3)

    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_simple_melody(AM_PENT, root, bpm, total_bars, intro_s, seed=404)
    piano = _place_notes(melody, n, piano_note)

    # Distant rain (not heavy — this is the "empty" feel)
    rain = rain_layer(n, gain=0.025, intensity=0.6)

    # Minimal tabla
    tabla = dholak_pattern(n, bpm=bpm, gain=0.04)

    swell = _dynamic_swell(n, depth=0.2)

    mix = pads + piano * 2.2 + rain + tabla * 0.3
    mix[0] *= swell
    mix[1] *= swell
    mix = simple_reverb(mix, wet=0.4)

    return master(mix, "tanhai_ka_safar.wav")


# ═══════════════════════════════════════════════════════════════
# TRACK 5: 😢 Dukh ka Dariya — Deep Piano + Rain + Tabla
# The one that makes you cry. Simple, deep, devastating.
# ═══════════════════════════════════════════════════════════════

def build_dukh_ka_dariya():
    np.random.seed(505)
    n = int(SR * DUR)
    bpm = 50
    root = 55  # G minor
    intro_s = 5.0

    # Gm - Eb - Bb - F (the saddest progression)
    Eb = [51, 55, 58]
    Bb = [46, 50, 53]
    F = [41, 45, 48]
    pads = _progression([Gm, Eb, Bb, F], chord_s=12.0, vol=0.6)

    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_simple_melody(GM_PENT, root, bpm, total_bars, intro_s, seed=505)
    piano = _place_notes(melody, n, piano_note)

    # Heavy rain + emotional tabla
    rain = rain_layer(n, gain=0.05, intensity=1.4)
    tabla = dholak_pattern(n, bpm=bpm, gain=0.07)

    # Big emotional swell
    swell = _dynamic_swell(n, depth=0.35)

    mix = pads + piano * 2.0 + rain + tabla * 0.5
    mix[0] *= swell
    mix[1] *= swell
    mix = simple_reverb(mix, wet=0.35)

    return master(mix, "dukh_ka_dariya.wav")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("🔥 VIRAL Background Music Generator")
    print("   Making music that people WANT to use in their videos!")
    print("   Key: Simple piano + Heavy rain + Gentle tabla = VIRAL")
    print()
    paths = [
        build_barish_piano_viral(),   # 🌧️ THE viral one
        build_raat_ka_dard(),         # 🌙 Deep sad violin
        build_judai_ka_mausam(),      # 💔 Heartbreak feel
        build_tanhai_ka_safar(),      # 🏜️ Empty lonely
        build_dukh_ka_dariya(),       # 😢 The one that makes you cry
    ]
    print(f"\n✅ Done — {len(paths)} VIRAL tracks!")
    print("   These are the kind people USE as background music on TikTok/Reels.")
    print("   Simple piano + rain + tabla = the formula that works.")


if __name__ == "__main__":
    main()
