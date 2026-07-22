#!/usr/bin/env python3
"""Generate ORIGINAL, 100% copyright-free ambient music beds for Khateb-Ishq.

Why this exists: the pipeline needs a safe sad-music bed under the narration,
but downloading tracks (even 'no copyright' ones) keeps a license-verification
burden forever. These tracks are synthesized note-by-note with numpy — every
sample is computed here, no external audio is used, so the output is an
original work of this project. Nothing to attribute, nothing to strike.

Usage:  python scripts/generate_music_beds.py
Output: assets/music/barish_rain_gm.wav  (rain + minor pads)
        assets/music/tanhai_piano_am.wav (minor pads + sparse sad piano)
        assets/music/raat_drone_em.wav   (deep drone + distant piano + faint rain)
Format: WAV, 22050 Hz, mono, 16-bit — small files, perfect under speech at
MUSIC_VOLUME=0.08.
"""

import os
import wave

import numpy as np

SR = 22050          # sample rate — plenty for a background bed under voice
DUR = 60.0          # seconds per track (videos loop it if longer)
OUT_DIR = os.path.join("assets", "music")


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _env_cos(n: int, ramp_s: float) -> np.ndarray:
    """Raised-cosine fade-in/out so chords blend without clicks."""
    env = np.ones(n)
    r = min(int(SR * ramp_s), n // 2)
    if r > 0:
        env[:r] = 0.5 - 0.5 * np.cos(np.pi * np.arange(r) / r)
        env[-r:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return env


def pad_chord(midis, dur: float, attack: float = 1.5) -> np.ndarray:
    """Soft analog-ish pad chord: detuned sines + gentle octave shimmer."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    seg = np.zeros(n)
    for m in midis:
        f = hz(m)
        det = 1.0 + np.random.uniform(-0.002, 0.002)
        seg += np.sin(2 * np.pi * f * det * t) + 0.30 * np.sin(2 * np.pi * 2.0 * f * t)
    seg /= max(len(midis), 1)
    return seg * _env_cos(n, attack)


def progression(chords, chord_s: float = 12.0, cross: float = 1.5, vol: float = 1.6) -> np.ndarray:
    """Overlap-add a chord progression across the whole track."""
    n = int(SR * DUR)
    out = np.zeros(n)
    start = 0.0
    seglen = chord_s + cross
    for ch in chords:
        seg = pad_chord(ch, seglen, attack=cross)
        idx = int(start * SR)
        L = min(len(seg), n - idx)
        if L > 0:
            out[idx: idx + L] += seg[:L]
        start += chord_s
        if start >= DUR:
            break
    return vol * out


def sparse_piano(scale_midis, vol: float = 0.22, tau: float = 1.4,
                 gap=(2.5, 6.5), octaves=(0, 12)) -> np.ndarray:
    """Sparse 'felt piano': random pentatonic notes with fast attack, long decay."""
    n = int(SR * DUR)
    sig = np.zeros(n)
    t_cursor = np.random.uniform(1.0, 3.0)
    while t_cursor < DUR - 3.0:
        m = float(np.random.choice(scale_midis)) + 12.0 * np.random.choice(octaves)
        f = hz(m)
        L = int(SR * 3.5)
        tt = np.arange(L) / SR
        env = np.exp(-tt / tau)
        atk = int(SR * 0.012)
        env[:atk] *= tt[:atk] / 0.012
        note = (np.sin(2 * np.pi * f * tt) + 0.28 * np.sin(2 * np.pi * 3.0 * f * tt)) * env
        idx = int(t_cursor * SR)
        L2 = min(L, n - idx)
        sig[idx: idx + L2] += note[:L2]
        t_cursor += np.random.uniform(*gap)
    return vol * sig


def rain(vol: float = 0.06, body: float = 1.0) -> np.ndarray:
    """Soft steady rain: low-passed noise with slow amplitude wander."""
    n = int(SR * DUR)
    x = np.random.randn(n)
    k = np.hanning(401)
    k /= k.sum()
    y = np.convolve(x, k, mode="same")
    y /= np.abs(y).max() + 1e-9
    mod = np.convolve(np.random.randn(n), np.hanning(int(SR * 2)), mode="same")
    mod /= np.abs(mod).max() + 1e-9
    return vol * body * y * (0.55 + 0.45 * mod)


def master(sig: np.ndarray, name: str) -> str:
    """Soft-limit, fade, normalize to -3 dBFS, write 16-bit mono WAV."""
    sig = np.tanh(sig * 1.1)
    f = int(SR * 2.0)
    sig[:f] *= np.linspace(0.0, 1.0, f)
    sig[-f:] *= np.linspace(1.0, 0.0, f)
    peak = np.abs(sig).max() or 1.0
    pcm = (sig / peak * 0.70 * 32767).astype(np.int16)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  wrote {path}  ({DUR:.0f}s, {os.path.getsize(path)//1024} KB)")
    return path


# --- Chord tables (MIDI note numbers) --------------------------------------
Gm = [55, 58, 62, 65]   # G3 Bb3 D4 G4
Eb = [51, 55, 58, 63]   # Eb3 G3 Bb3 Eb4
Bb = [46, 50, 53, 58]   # Bb2 D3 F3 Bb3
F  = [41, 45, 48, 53]   # F2 A2 C3 F3
Am = [45, 48, 52, 57]   # A2 C3 E3 A3
C  = [48, 52, 55, 60]   # C3 E3 G3 C4
Em = [40, 47, 52, 55]   # E2 B2 E3 G3

GM_PENT = [55, 58, 60, 62, 65]      # G Bb C D G
AM_PENT = [57, 60, 62, 64, 69]      # A C D E A
EM_PENT = [52, 55, 57, 59, 64]      # E G A B E


def build_barish():
    np.random.seed(101)
    sig = progression([Gm, Eb, Bb, F], vol=1.7) + sparse_piano(GM_PENT, vol=0.10, gap=(5.0, 9.0)) + rain(0.065)
    return master(sig, "barish_rain_gm.wav")


def build_tanhai():
    np.random.seed(202)
    sig = progression([Am, F, C, Em], vol=1.5) + sparse_piano(AM_PENT, vol=0.24, gap=(2.8, 6.0))
    return master(sig, "tanhai_piano_am.wav")


def build_raat():
    np.random.seed(303)
    n = int(SR * DUR)
    t = np.arange(n) / SR
    drone = pad_chord(Em, DUR, attack=6.0) * (1.0 + 0.06 * np.sin(2 * np.pi * 0.02 * t))
    sig = 2.2 * drone + sparse_piano(EM_PENT, vol=0.16, gap=(6.0, 11.0), octaves=(0, -12)) + rain(0.03)
    return master(sig, "raat_drone_em.wav")


def main():
    print("Synthesizing original Khateb-Ishq music beds (numpy only, no samples)...")
    paths = [build_barish(), build_tanhai(), build_raat()]
    print(f"Done — {len(paths)} tracks in {OUT_DIR}/. 100% original: no attribution needed, no claim risk.")


if __name__ == "__main__":
    main()
