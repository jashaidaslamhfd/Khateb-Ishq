#!/usr/bin/env python3
"""
Khateb-Ishq — Pure Acoustic Solo Piano & Rain Master Engine.

ZERO VOCAL HUMMING / ZERO SYNTH FLUTE:
  - 100% Pure Acoustic Piano Keystrokes (Natural hammer attack & physical string decay)
  - Pure Ambient Rain Texture (Soft, soothing, no electronic noise)
  - Clean Piano Chord Progressions: A Minor -> D Minor -> F Major -> E7 (Deep Sadness)
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


# ── PURE ACOUSTIC GRAND PIANO MODEL ──
def acoustic_grand_piano(freq: float, duration: float, vel: float = 0.7) -> np.ndarray:
    """Generates an authentic acoustic piano note with natural physical string decay."""
    t = np.linspace(0, duration, int(SR * duration), False)
    
    # Natural multi-rate string damping (higher harmonics decay faster)
    decay_fund = np.exp(-t / 2.8)
    decay_h2 = np.exp(-t / 1.4)
    decay_h3 = np.exp(-t / 0.8)
    decay_h4 = np.exp(-t / 0.4)
    
    # Inharmonic piano string overtones (physical stiffness)
    f0 = freq
    f1 = freq * 2.0015
    f2 = freq * 3.0035
    f3 = freq * 4.0070
    
    sig = (1.00 * np.sin(2 * np.pi * f0 * t) * decay_fund +
           0.50 * np.sin(2 * np.pi * f1 * t) * decay_h2 +
           0.22 * np.sin(2 * np.pi * f2 * t) * decay_h3 +
           0.08 * np.sin(2 * np.pi * f3 * t) * decay_h4)
    
    # Felt hammer attack
    att_len = int(SR * 0.005)
    env = np.ones_like(sig)
    env[:att_len] = np.sin(np.linspace(0, np.pi / 2, att_len))
    return sig * env * vel


# ── NATURAL RAIN AMBIENCE ──
def natural_rain(duration: float) -> np.ndarray:
    n = int(SR * duration)
    # Filtered brown/pink noise
    noise = np.random.normal(0, 0.08, n)
    b, a = signal.butter(2, 1400 / (SR / 2), btype='low')
    return signal.lfilter(b, a, noise) * 0.15


def build_pure_piano_master():
    print("🎹 Generating 100% Pure Acoustic Piano & Rain Track (Zero Synth Flute / Zero Humming)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    # Gentle background rain
    mix += natural_rain(DUR)
    
    # Heartbreaking Sad Piano Progression (Am -> Dm -> F -> E7)
    # Slow, spacious, emotional keystrokes
    chords = [
        # (Bass Note, Melody Arpeggios)
        (45, [57, 60, 64, 69, 72]),  # A1 + (A3, C4, E4, A4, C5)
        (38, [50, 53, 57, 62, 65]),  # D1 + (D3, F3, A3, D4, F4)
        (41, [53, 57, 60, 65, 69]),  # F1 + (F3, A3, C4, F4, A4)
        (40, [52, 56, 59, 64, 68]),  # E1 + (E3, G#3, B3, E4, G#4)
    ]
    
    step_s = 5.2
    for loop in range(int(DUR / (step_s * len(chords))) + 1):
        for c_i, (bass_midi, melody_notes) in enumerate(chords):
            start_t = (loop * len(chords) + c_i) * step_s
            if start_t >= DUR - 3:
                break
            idx = int(start_t * SR)
            
            # Deep soft bass piano note
            bass_sig = acoustic_grand_piano(hz(bass_midi), duration=5.0, vel=0.55)
            end_b = min(total_n, idx + len(bass_sig))
            mix[idx:end_b] += bass_sig[:end_b - idx]
            
            # Slow delicate melody droplets (falling like tears)
            for m_i, m_note in enumerate(melody_notes):
                offset = int((0.35 + m_i * 0.55) * SR)
                m_sig = acoustic_grand_piano(hz(m_note), duration=4.0, vel=0.65 - m_i * 0.06)
                m_end = min(total_n, idx + offset + len(m_sig))
                if m_end > idx + offset:
                    mix[idx + offset:m_end] += m_sig[:m_end - (idx + offset)]

    # Clean Stereo Spread (Pure delay, zero feedback)
    delay_samples = int(SR * 0.025)
    left = mix
    right = np.zeros_like(mix)
    right[delay_samples:] = mix[:-delay_samples]
    stereo = np.column_stack([left, right])
    
    out_path = os.path.join(OUT_DIR, "viral_tiktok_sad_flute_violin_beat.wav")
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.75
    int_data = (stereo * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(int_data.tobytes())
    print(f"✅ Generated Pure Acoustic Master: {out_path}")


if __name__ == "__main__":
    build_pure_piano_master()
