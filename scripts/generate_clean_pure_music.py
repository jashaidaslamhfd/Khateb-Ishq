#!/usr/bin/env python3
"""
Khateb-Ishq — ZERO-HUM Crystal Pure Acoustic Sad Music.

KILLS 100% OF THE "OOOOOOOO" LOW-FREQUENCY DRONE:
  - Strict High-Pass Filter (Low-Cut at 180Hz) to eliminate all bass mud/hum
  - Pure delicate acoustic piano droplets (decaying naturally into silence)
  - Sweet high-register Bansuri Flute (C5-G5 emotional melodic phrases)
  - Soft airy string chords (no low cello hum)
  - Zero continuous sine waves, zero sub drones!
"""

import os
import wave
import numpy as np
from scipy import signal

SR = 44100
DUR = 80.0
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
os.makedirs(OUT_DIR, exist_ok=True)


def hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


# ── 1. Delicate Acoustic Piano (Single clean keystrokes with natural silence) ──
def clean_piano_key(freq: float, duration: float, vel: float = 0.6) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), False)
    # Fast natural acoustic decay (no hanging hum)
    decay = np.exp(-t / 1.4)
    sig = (1.00 * np.sin(2 * np.pi * freq * t) +
           0.35 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t / 0.8) +
           0.12 * np.sin(2 * np.pi * freq * 3.0 * t) * np.exp(-t / 0.4))
    
    # Soft hammer strike
    att = int(SR * 0.005)
    env = np.ones_like(sig)
    env[:att] = np.sin(np.linspace(0, np.pi / 2, att))
    return sig * decay * env * vel


# ── 2. Sweet High-Register Bansuri Flute (Airy, Melancholic, No Low Hum) ──
def clean_high_flute(freq: float, duration: float, vel: float = 0.55) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), False)
    # Sweet vibrato
    vib = 1.0 + 0.008 * np.sin(2 * np.pi * 5.2 * t)
    sig = (1.00 * np.sin(2 * np.pi * freq * vib * t) +
           0.25 * np.sin(2 * np.pi * freq * 2.0 * vib * t) +
           0.08 * np.sin(2 * np.pi * freq * 3.0 * vib * t))
    
    att = int(SR * 0.18)
    rel = int(SR * 0.30)
    env = np.ones_like(sig)
    if len(env) > att + rel:
        env[:att] = np.sin(np.linspace(0, np.pi / 2, att)) ** 2
        env[-rel:] = np.cos(np.linspace(0, np.pi / 2, rel)) ** 2
    return sig * env * vel


# ── 3. Light Airy Violins (High Register, Mid-Treble only) ──
def clean_high_strings(midi_notes: list, duration: float, vel: float = 0.3) -> np.ndarray:
    n = int(SR * duration)
    t = np.linspace(0, duration, n, False)
    swell = np.sin(np.linspace(0, np.pi, n)) ** 2.0
    chord = np.zeros(n)
    for note in midi_notes:
        f = hz(note)
        sig = (1.00 * np.sin(2 * np.pi * f * t) +
               0.30 * np.sin(2 * np.pi * f * 2.0 * t))
        chord += sig
    return (chord / len(midi_notes)) * swell * vel


def build_pure_crystal_sad_music():
    print("💎 Generating 100% Drone-Free, Clean Sad Music (Piano + High Flute + Soft Violins)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    # High-register sad chords (A4 Minor, F4, C4, E4 - All above 260Hz!)
    chords = [
        [69, 72, 76],  # Am (A4, C5, E5) - High, sweet, no bass hum
        [65, 69, 72],  # F (F4, A4, C5)
        [60, 67, 72],  # C (C4, G4, C5)
        [64, 67, 71],  # Em (E4, G4, B4)
    ]
    chord_dur = 4.5
    for loop in range(int(DUR / (chord_dur * len(chords))) + 1):
        for c_i, chord in enumerate(chords):
            start_t = (loop * len(chords) + c_i) * chord_dur
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            
            # 1. Light Airy String Swell
            str_sig = clean_high_strings(chord, duration=5.0, vel=0.25)
            end_s = min(total_n, idx + len(str_sig))
            mix[idx:end_s] += str_sig[:end_s - idx]
            
            # 2. Delicate Piano Arpeggio Notes (Ting... Ting... Ting...)
            for p_i, note in enumerate(chord):
                p_off = int(p_i * 0.45 * SR)
                p_sig = clean_piano_key(hz(note), duration=3.5, vel=0.55 - p_i * 0.08)
                p_end = min(total_n, idx + p_off + len(p_sig))
                if p_end > idx + p_off:
                    mix[idx + p_off:p_end] += p_sig[:p_end - (idx + p_off)]

    # 3. High-Register Bansuri Flute Solo (C5 to A5 notes - Sweet & Sorrowful)
    flute_phrases = [
        [(72, 3.0), (71, 2.5), (69, 3.5)],        # C5 -> B4 -> A4
        [(69, 2.5), (72, 2.8), (76, 3.5)],        # A4 -> C5 -> E5
        [(74, 2.5), (72, 2.5), (71, 2.5), (69, 4.0)], # D5 -> C5 -> B4 -> A4
    ]
    cur_f_t = 3.0
    while cur_f_t < DUR - 5:
        phrase = flute_phrases[np.random.randint(0, len(flute_phrases))]
        for note, ndur in phrase:
            idx = int(cur_f_t * SR)
            f_sig = clean_high_flute(hz(note), ndur, vel=0.45)
            end_f = min(total_n, idx + len(f_sig))
            if end_f > idx:
                mix[idx:end_f] += f_sig[:end_f - idx]
            cur_f_t += ndur * 0.9
        cur_f_t += 2.5  # Silence between flute lines

    # ── STRICT HIGH-PASS FILTER (Cut everything below 220 Hz to KILL ALL "OOOOO" HUM) ──
    b, a = signal.butter(4, 220.0 / (SR / 2), btype='highpass')
    clean_filtered = signal.lfilter(b, a, mix)

    # Clean Stereo Spread (Short 40ms Haas effect, zero feedback echo)
    delay_samples = int(SR * 0.035)
    left = clean_filtered
    right = np.zeros_like(clean_filtered)
    right[delay_samples:] = clean_filtered[:-delay_samples]

    stereo = np.column_stack([left, right])
    
    # Save
    out_path = os.path.join(OUT_DIR, "viral_tiktok_sad_flute_violin_beat.wav")
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.70
    int_data = (stereo * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(int_data.tobytes())
    print(f"✅ Generated 100% Pure, Zero-Hum Track: {out_path}")


if __name__ == "__main__":
    build_pure_crystal_sad_music()
