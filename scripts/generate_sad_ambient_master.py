#!/usr/bin/env python3
"""
Khateb-Ishq — Fast Vectorized Acoustic Sad Music Generator.

Generates cinema-grade, soulful, acoustic ambient background music beds
specifically engineered for Urdu Sad Poetry / Mushaira recitals.

Vectorized with NumPy & SciPy for ultra-fast rendering.
"""

import math
import os
import wave
import numpy as np
from scipy import signal

SR = 44100
DUR = 75.0  # 75s
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
os.makedirs(OUT_DIR, exist_ok=True)


def hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def apply_fast_reverb(mono_signal: np.ndarray, decay_s: float = 2.2) -> np.ndarray:
    """Fast vectorized convolution reverb using synthesized stereo room impulse response."""
    ir_len = int(SR * decay_s)
    t = np.linspace(0, decay_s, ir_len, False)
    decay = np.exp(-t / (decay_s * 0.4))
    
    # Left & Right slightly decorrelated noise bursts
    noise_l = np.random.normal(0, 1.0, ir_len) * decay
    noise_r = np.random.normal(0, 1.0, ir_len) * decay
    
    # Lowpass filter the impulse response to emulate warm room reflections
    b, a = signal.butter(3, 2500 / (SR / 2), btype='low')
    ir_l = signal.lfilter(b, a, noise_l)
    ir_r = signal.lfilter(b, a, noise_r)
    
    # Fast FFT convolution
    rev_l = signal.fftconvolve(mono_signal, ir_l, mode='full')[:len(mono_signal)]
    rev_r = signal.fftconvolve(mono_signal, ir_r, mode='full')[:len(mono_signal)]
    
    # Normalize wet
    norm_l = np.max(np.abs(rev_l)) or 1.0
    norm_r = np.max(np.abs(rev_r)) or 1.0
    
    dry = mono_signal
    stereo = np.column_stack([
        0.60 * dry + 0.40 * (rev_l / norm_l * np.max(np.abs(dry))),
        0.60 * dry + 0.40 * (rev_r / norm_r * np.max(np.abs(dry)))
    ])
    return stereo


def generate_piano_note(freq: float, duration: float, vel: float = 0.8) -> np.ndarray:
    """Rich acoustic piano modeling: fundamental + inharmonic string overtones."""
    t = np.linspace(0, duration, int(SR * duration), False)
    decay = np.exp(-t / (1.8 + 80.0 / (freq + 10.0)))
    
    sig = (1.00 * np.sin(2 * np.pi * freq * t) +
           0.60 * np.sin(2 * np.pi * freq * 2.001 * t) * np.exp(-t / 1.2) +
           0.30 * np.sin(2 * np.pi * freq * 3.003 * t) * np.exp(-t / 0.8) +
           0.15 * np.sin(2 * np.pi * freq * 4.006 * t) * np.exp(-t / 0.5))
    
    attack_len = int(SR * 0.008)
    attack_env = np.ones_like(sig)
    attack_env[:attack_len] = np.sin(np.linspace(0, np.pi / 2, attack_len))
    return sig * decay * attack_env * vel


def generate_flute_note(freq: float, duration: float) -> np.ndarray:
    """Acoustic Bamboo Flute (Bansuri) modeling with breath turbulence and vibrato."""
    t = np.linspace(0, duration, int(SR * duration), False)
    vibrato = 1.0 + 0.012 * np.sin(2 * np.pi * 5.2 * t) * (1.0 - np.exp(-t / 0.5))
    breath = np.random.normal(0, 0.03, len(t))
    
    sig = (1.00 * np.sin(2 * np.pi * freq * vibrato * t) +
           0.40 * np.sin(2 * np.pi * freq * 2.0 * vibrato * t) +
           0.12 * np.sin(2 * np.pi * freq * 3.0 * vibrato * t) +
           breath)
    
    attack = int(SR * 0.25)
    release = int(SR * 0.40)
    env = np.ones_like(sig)
    if len(env) > attack + release:
        env[:attack] = np.sin(np.linspace(0, np.pi / 2, attack)) ** 2
        env[-release:] = np.cos(np.linspace(0, np.pi / 2, release)) ** 2
    return sig * env * 0.75


def generate_rain_ambience(duration: float) -> np.ndarray:
    """Warm binaural rain & distant storm ambiance."""
    n = int(SR * duration)
    white = np.random.normal(0, 0.15, n)
    b, a = signal.butter(2, 1800 / (SR / 2), btype='low')
    rain = signal.lfilter(b, a, white)
    return rain * 0.35


# ─────────────────────────────────────────────────────────────
# 1. Track: Dil Ka Gham (Acoustic Reverb Piano in A Minor)
# ─────────────────────────────────────────────────────────────
def build_dil_ka_gham_piano():
    print("🎹 Generating: dil_ka_gham_piano.wav...")
    total_samples = int(SR * DUR)
    mono = np.zeros(total_samples)
    
    chords = [
        [57, 60, 64, 69],  # A Minor
        [53, 57, 60, 65],  # F Major
        [48, 55, 60, 64],  # C Major
        [52, 55, 59, 64],  # E Minor
    ]
    
    step_s = 4.5
    for loop in range(int(DUR / (step_s * len(chords))) + 1):
        for c_idx, chord in enumerate(chords):
            start_t = (loop * len(chords) + c_idx) * step_s
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            for n_idx, note in enumerate(chord):
                arpeggio_offset = int(n_idx * 0.12 * SR)
                note_dur = min(6.0, DUR - start_t)
                note_sig = generate_piano_note(hz(note), note_dur, vel=0.7 - n_idx * 0.08)
                end_idx = min(total_samples, idx + arpeggio_offset + len(note_sig))
                avail_len = end_idx - (idx + arpeggio_offset)
                if avail_len > 0:
                    mono[idx + arpeggio_offset:end_idx] += note_sig[:avail_len]

    mono += generate_rain_ambience(DUR) * 0.3
    stereo = apply_fast_reverb(mono, decay_s=2.5)
    save_wav("dil_ka_gham_piano.wav", stereo)


# ─────────────────────────────────────────────────────────────
# 2. Track: Tanhai Flute Ambient (Bansuri Melancholy in D Minor)
# ─────────────────────────────────────────────────────────────
def build_tanhai_flute():
    print("🎋 Generating: tanhai_flute_ambient.wav...")
    total_samples = int(SR * DUR)
    mono = np.zeros(total_samples)
    
    flute_phrases = [
        [(62, 3.5), (65, 3.0), (64, 4.0)],
        [(60, 2.5), (62, 3.0), (57, 4.5)],
        [(65, 3.0), (67, 3.0), (69, 4.0), (65, 3.5)],
        [(64, 2.5), (62, 3.5), (57, 5.0)],
    ]
    
    cur_t = 1.0
    while cur_t < DUR - 5:
        phrase = flute_phrases[np.random.randint(0, len(flute_phrases))]
        for note, ndur in phrase:
            idx = int(cur_t * SR)
            note_sig = generate_flute_note(hz(note), ndur)
            end_idx = min(total_samples, idx + len(note_sig))
            avail = end_idx - idx
            if avail > 0:
                mono[idx:end_idx] += note_sig[:avail]
            cur_t += ndur * 0.85
        cur_t += 2.0
        
    t = np.linspace(0, DUR, total_samples, False)
    drone = 0.25 * np.sin(2 * np.pi * hz(38) * t) + 0.12 * np.sin(2 * np.pi * hz(45) * t)
    mono += drone
    
    stereo = apply_fast_reverb(mono, decay_s=2.8)
    save_wav("tanhai_flute_ambient.wav", stereo)


# ─────────────────────────────────────────────────────────────
# 3. Track: Judai Sad Strings (Sarangi / Cello Swell Bed)
# ─────────────────────────────────────────────────────────────
def build_judai_strings():
    print("🎻 Generating: judai_sad_strings.wav...")
    total_samples = int(SR * DUR)
    mono = np.zeros(total_samples)
    
    progression = [
        [43, 50, 55, 58],  # G Minor
        [38, 45, 50, 53],  # D Minor
        [46, 50, 53, 58],  # Bb Major
        [41, 48, 53, 57],  # F Major
    ]
    
    step_s = 6.0
    for loop in range(int(DUR / (step_s * len(progression))) + 1):
        for c_idx, chord in enumerate(progression):
            start_t = (loop * len(progression) + c_idx) * step_s
            if start_t >= DUR - 3:
                break
            idx = int(start_t * SR)
            for note in chord:
                dur_s = 7.5
                tt = np.linspace(0, dur_s, int(SR * dur_s), False)
                swell = np.sin(np.linspace(0, np.pi, len(tt))) ** 2
                f = hz(note)
                vib = 1.0 + 0.008 * np.sin(2 * np.pi * 4.8 * tt)
                string_sig = (1.0 * np.sin(2 * np.pi * f * vib * tt) +
                              0.5 * np.sin(2 * np.pi * f * 2.0 * vib * tt) +
                              0.25 * np.sin(2 * np.pi * f * 3.0 * vib * tt)) * swell * 0.3
                end_idx = min(total_samples, idx + len(string_sig))
                avail = end_idx - idx
                if avail > 0:
                    mono[idx:end_idx] += string_sig[:avail]
                    
    stereo = apply_fast_reverb(mono, decay_s=3.0)
    save_wav("judai_sad_strings.wav", stereo)


def save_wav(filename: str, stereo_data: np.ndarray):
    path = os.path.join(OUT_DIR, filename)
    peak = np.max(np.abs(stereo_data))
    if peak > 0:
        stereo_data = stereo_data / peak * 0.85
    int_data = (stereo_data * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(int_data.tobytes())
    print(f"✅ Saved Master Audio Bed: {path} ({os.path.getsize(path) / 1024 / 1024:.1f} MB)")


def main():
    print("🎵 BUILDING CINEMA-GRADE ACOUSTIC SAD MUSIC FOR KHATEB-ISHQ...")
    build_dil_ka_gham_piano()
    build_tanhai_flute()
    build_judai_strings()
    print("🎉 ALL STUDIO MUSIC TRACKS GENERATED IN assets/music/!")


if __name__ == "__main__":
    main()
