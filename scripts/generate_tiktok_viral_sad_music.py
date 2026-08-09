#!/usr/bin/env python3
"""
Khateb-Ishq — Viral TikTok/Reels Multi-Instrument Sad Music Engine.

Generates the exact signature soundscape used by top viral Urdu poetry creators:
  • Soulful Bamboo Flute (Bansuri in Raag Bhairavi/Darbari with human vibrato)
  • Emotional Violins / Cello / Sarangi String Swells
  • Slow 58-62 BPM Heartbeat Drum / Soft Desi Tabla Kick
  • Reverb-Drenched Minor-Key Piano Chords
  • Atmospheric Rain / Vinyl Textures
"""

import math
import os
import wave
import numpy as np
from scipy import signal

SR = 44100
DUR = 80.0  # 80 seconds (covers up to 60s Shorts + intro/outro fades)
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
os.makedirs(OUT_DIR, exist_ok=True)


def hz(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def apply_lush_studio_reverb(mono_signal: np.ndarray, decay_s: float = 3.0, wet: float = 0.45) -> np.ndarray:
    """Stereo convolution reverb that gives that vast, emotional, cinematic room depth."""
    ir_len = int(SR * decay_s)
    t = np.linspace(0, decay_s, ir_len, False)
    decay = np.exp(-t / (decay_s * 0.35))
    
    # Left & right slightly decorrelated reflections
    noise_l = np.random.normal(0, 1.0, ir_len) * decay
    noise_r = np.random.normal(0, 1.0, ir_len) * decay
    
    # Warm analog room damping filter (lowpass at 3200Hz)
    b, a = signal.butter(2, 3200 / (SR / 2), btype='low')
    ir_l = signal.lfilter(b, a, noise_l)
    ir_r = signal.lfilter(b, a, noise_r)
    
    rev_l = signal.fftconvolve(mono_signal, ir_l, mode='full')[:len(mono_signal)]
    rev_r = signal.fftconvolve(mono_signal, ir_r, mode='full')[:len(mono_signal)]
    
    max_dry = np.max(np.abs(mono_signal)) or 1.0
    norm_l = np.max(np.abs(rev_l)) or 1.0
    norm_r = np.max(np.abs(rev_r)) or 1.0
    
    dry = mono_signal
    stereo = np.column_stack([
        (1.0 - wet) * dry + wet * (rev_l / norm_l * max_dry),
        (1.0 - wet) * dry + wet * (rev_r / norm_r * max_dry)
    ])
    return stereo


# ── INSTRUMENT 1: Acoustic Bansuri / Flute with Breath Vibrato ──
def synth_flute_note(freq: float, duration: float, vel: float = 0.8) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), False)
    # Natural breath vibrato (5.4 Hz, begins after 0.25s)
    vib_onset = np.clip((t - 0.25) / 0.5, 0.0, 1.0)
    vibrato = 1.0 + 0.015 * np.sin(2 * np.pi * 5.4 * t) * vib_onset
    breath = np.random.normal(0, 0.035, len(t))
    
    sig = (1.00 * np.sin(2 * np.pi * freq * vibrato * t) +
           0.45 * np.sin(2 * np.pi * freq * 2.0 * vibrato * t) * np.exp(-t / 3.0) +
           0.18 * np.sin(2 * np.pi * freq * 3.0 * vibrato * t) * np.exp(-t / 2.0) +
           breath)
    
    # Smooth attack and release envelope
    attack = int(SR * 0.20)
    release = int(SR * 0.35)
    env = np.ones_like(sig)
    if len(env) > attack + release:
        env[:attack] = np.sin(np.linspace(0, np.pi / 2, attack)) ** 2
        env[-release:] = np.cos(np.linspace(0, np.pi / 2, release)) ** 2
    return sig * env * vel


# ── INSTRUMENT 2: Emotional Violins / Sarangi Swell ──
def synth_string_chord(midi_notes: list, duration: float, vel: float = 0.7) -> np.ndarray:
    n = int(SR * duration)
    t = np.linspace(0, duration, n, False)
    # Slow dynamic bow swell
    swell = np.sin(np.linspace(0, np.pi, n)) ** 1.6
    chord_sig = np.zeros(n)
    
    for note in midi_notes:
        f = hz(note)
        vib = 1.0 + 0.008 * np.sin(2 * np.pi * 4.8 * t)
        note_sig = (1.00 * np.sin(2 * np.pi * f * vib * t) +
                    0.55 * np.sin(2 * np.pi * f * 2.0 * vib * t) +
                    0.28 * np.sin(2 * np.pi * f * 3.0 * vib * t) +
                    0.12 * np.sin(2 * np.pi * f * 4.0 * vib * t))
        chord_sig += note_sig
        
    return (chord_sig / len(midi_notes)) * swell * vel


# ── INSTRUMENT 3: Deep Reverb Acoustic Piano ──
def synth_piano_note(freq: float, duration: float, vel: float = 0.75) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), False)
    decay = np.exp(-t / (1.6 + 60.0 / (freq + 10.0)))
    sig = (1.00 * np.sin(2 * np.pi * freq * t) +
           0.55 * np.sin(2 * np.pi * freq * 2.001 * t) * np.exp(-t / 1.1) +
           0.25 * np.sin(2 * np.pi * freq * 3.003 * t) * np.exp(-t / 0.7) +
           0.10 * np.sin(2 * np.pi * freq * 4.005 * t) * np.exp(-t / 0.4))
    
    att = int(SR * 0.006)
    env = np.ones_like(sig)
    env[:att] = np.sin(np.linspace(0, np.pi / 2, att))
    return sig * decay * env * vel


# ── INSTRUMENT 4: Slow 60 BPM Soft Heartbeat / Desi Low Drum ──
def synth_soft_drum_kick() -> np.ndarray:
    dur = 0.65
    t = np.linspace(0, dur, int(SR * dur), False)
    # Pitch drop: 110Hz -> 42Hz sub bass
    freq_drop = 42.0 + 68.0 * np.exp(-t / 0.08)
    phase = 2 * np.pi * np.cumsum(freq_drop) / SR
    sub = np.sin(phase) * np.exp(-t / 0.22)
    # Soft thud tap
    click = np.random.normal(0, 0.15, len(t)) * np.exp(-t / 0.02)
    return (sub * 0.85 + click * 0.15) * 0.6


def synth_soft_rim_tap() -> np.ndarray:
    dur = 0.25
    t = np.linspace(0, dur, int(SR * dur), False)
    tap = np.sin(2 * np.pi * 380 * t) * np.exp(-t / 0.03) + np.random.normal(0, 0.1, len(t)) * np.exp(-t / 0.02)
    return tap * 0.25


# ── TEXTURE: Aesthetic Rain & Warm Low Drone ──
def synth_rain_and_sub_drone(duration: float) -> np.ndarray:
    n = int(SR * duration)
    t = np.linspace(0, duration, n, False)
    white = np.random.normal(0, 0.12, n)
    b, a = signal.butter(2, 1600 / (SR / 2), btype='low')
    rain = signal.lfilter(b, a, white)
    # Warm sub-bass foundation (C2 / G2 drone)
    sub = 0.22 * np.sin(2 * np.pi * hz(36) * t) + 0.12 * np.sin(2 * np.pi * hz(43) * t)
    return rain * 0.25 + sub


# ─────────────────────────────────────────────────────────────
# 1. TRACK: viral_tiktok_sad_flute_violin_beat.wav (THE SIGNATURE ONE)
# ─────────────────────────────────────────────────────────────
def build_signature_viral_track():
    print("🎬 Generating: viral_tiktok_sad_flute_violin_beat.wav (Flute + Violins + Drums + Piano)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    # 1. Add background rain + warm analog sub drone
    mix += synth_rain_and_sub_drone(DUR)
    
    # 2. Chord Progression (A Minor Sad Progression: Am -> F -> C -> G/Em)
    chord_prog = [
        [57, 60, 64, 69],  # Am
        [53, 57, 60, 65],  # F
        [48, 55, 60, 64],  # C
        [55, 59, 62, 67],  # G
    ]
    chord_dur = 4.8
    for loop in range(int(DUR / (chord_dur * len(chord_prog))) + 1):
        for c_i, chord in enumerate(chord_prog):
            start_t = (loop * len(chord_prog) + c_i) * chord_dur
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            
            # Add Violin String Swell
            str_sig = synth_string_chord(chord, duration=5.8, vel=0.45)
            end_s = min(total_n, idx + len(str_sig))
            mix[idx:end_s] += str_sig[:end_s - idx]
            
            # Add Slow Arpeggiated Piano
            for p_i, note in enumerate(chord):
                p_offset = int(p_i * 0.35 * SR)
                p_sig = synth_piano_note(hz(note), duration=4.5, vel=0.6 - p_i * 0.08)
                p_end = min(total_n, idx + p_offset + len(p_sig))
                if p_end > idx + p_offset:
                    mix[idx + p_offset:p_end] += p_sig[:p_end - (idx + p_offset)]

    # 3. Slow 60 BPM Heartbeat Drums (Kick on Beat 1, Soft Tap on Beat 3)
    beat_interval = 1.0  # 60 BPM = 1.0s per beat
    cur_beat_t = 2.0
    kick = synth_soft_drum_kick()
    tap = synth_soft_rim_tap()
    while cur_beat_t < DUR - 3:
        idx_kick = int(cur_beat_t * SR)
        k_end = min(total_n, idx_kick + len(kick))
        mix[idx_kick:k_end] += kick[:k_end - idx_kick] * 0.75
        
        # Tap on offbeat
        idx_tap = int((cur_beat_t + 0.5) * SR)
        t_end = min(total_n, idx_tap + len(tap))
        if t_end > idx_tap:
            mix[idx_tap:t_end] += tap[:t_end - idx_tap] * 0.5
            
        cur_beat_t += 2.0  # Every 2 seconds slow heartbeat pace

    # 4. Soulful Melodic Flute (Bansuri Melancholy Phrases)
    flute_phrases = [
        [(69, 3.2), (67, 2.5), (65, 3.0), (64, 4.0)],
        [(65, 2.5), (64, 2.2), (60, 2.8), (57, 4.5)],
        [(64, 2.8), (67, 3.0), (69, 3.5), (72, 4.0)],
        [(71, 2.5), (69, 3.0), (65, 3.2), (64, 4.5)],
    ]
    cur_f_t = 3.0
    while cur_f_t < DUR - 6:
        phrase = flute_phrases[np.random.randint(0, len(flute_phrases))]
        for note, ndur in phrase:
            idx = int(cur_f_t * SR)
            f_sig = synth_flute_note(hz(note), ndur, vel=0.7)
            end_f = min(total_n, idx + len(f_sig))
            if end_f > idx:
                mix[idx:end_f] += f_sig[:end_f - idx]
            cur_f_t += ndur * 0.85
        cur_f_t += 2.2  # Breath pause between poetic lines

    # Apply vast studio reverb & master
    stereo = apply_lush_studio_reverb(mix, decay_s=2.8, wet=0.42)
    save_master_track("viral_tiktok_sad_flute_violin_beat.wav", stereo)


# ─────────────────────────────────────────────────────────────
# 2. TRACK: jaun_elia_style_darbari_cello.wav (DEEP SADNESS / RAAG DARBARI)
# ─────────────────────────────────────────────────────────────
def build_jaun_elia_darbari_track():
    print("🎻 Generating: jaun_elia_style_darbari_cello.wav (Darbari Flute + Heavy Cello Swells + Heartbeat)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    # Low Cello Drone (D Minor / D2 - D3)
    mix += synth_rain_and_sub_drone(DUR) * 1.2
    
    # Raag Darbari notes (D, E, F, G, A, Bb, C)
    cello_prog = [
        [38, 45, 50, 53],  # Dm
        [43, 50, 55, 58],  # Gm
        [41, 48, 53, 57],  # F
        [36, 43, 48, 52],  # C
    ]
    chord_dur = 5.2
    for loop in range(int(DUR / (chord_dur * len(cello_prog))) + 1):
        for c_i, chord in enumerate(cello_prog):
            start_t = (loop * len(cello_prog) + c_i) * chord_dur
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            str_sig = synth_string_chord(chord, duration=6.5, vel=0.55)
            end_s = min(total_n, idx + len(str_sig))
            mix[idx:end_s] += str_sig[:end_s - idx]
            
    # Slow Heartbeat Kick
    cur_beat = 1.5
    kick = synth_soft_drum_kick()
    while cur_beat < DUR - 3:
        idx = int(cur_beat * SR)
        k_end = min(total_n, idx + len(kick))
        mix[idx:k_end] += kick[:k_end - idx] * 0.7
        cur_beat += 2.2

    # Heart-wrenching Darbari Bansuri Solo
    darbari_phrases = [
        [(62, 3.5), (65, 3.0), (64, 4.2)],
        [(60, 2.5), (62, 3.2), (58, 2.5), (57, 5.0)],
        [(65, 3.0), (67, 3.2), (69, 4.0), (65, 3.8)],
        [(64, 2.8), (62, 3.5), (57, 5.5)],
    ]
    cur_f_t = 2.5
    while cur_f_t < DUR - 6:
        phrase = darbari_phrases[np.random.randint(0, len(darbari_phrases))]
        for note, ndur in phrase:
            idx = int(cur_f_t * SR)
            f_sig = synth_flute_note(hz(note), ndur, vel=0.75)
            end_f = min(total_n, idx + len(f_sig))
            if end_f > idx:
                mix[idx:end_f] += f_sig[:end_f - idx]
            cur_f_t += ndur * 0.88
        cur_f_t += 2.5

    stereo = apply_lush_studio_reverb(mix, decay_s=3.2, wet=0.46)
    save_master_track("jaun_elia_style_darbari_cello.wav", stereo)


# ─────────────────────────────────────────────────────────────
# 3. TRACK: tanhai_aesthetic_piano_violin_rain.wav (TIKTOK AESTHETIC RAIN)
# ─────────────────────────────────────────────────────────────
def build_tanhai_aesthetic_piano():
    print("🌧️ Generating: tanhai_aesthetic_piano_violin_rain.wav (Rain + Reverb Piano + Violins)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    # Heavy aesthetic rain
    mix += synth_rain_and_sub_drone(DUR) * 1.4
    
    piano_chords = [
        [57, 60, 64, 69],  # Am
        [53, 57, 60, 65],  # F
        [48, 55, 60, 64],  # C
        [52, 55, 59, 64],  # Em
    ]
    chord_dur = 4.2
    for loop in range(int(DUR / (chord_dur * len(piano_chords))) + 1):
        for c_i, chord in enumerate(piano_chords):
            start_t = (loop * len(piano_chords) + c_i) * chord_dur
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            
            # String backing
            str_sig = synth_string_chord(chord, duration=5.2, vel=0.38)
            end_s = min(total_n, idx + len(str_sig))
            mix[idx:end_s] += str_sig[:end_s - idx]
            
            # Crisp Piano Arpeggios (Tears falling vibe)
            for p_i, note in enumerate(chord):
                p_off = int(p_i * 0.28 * SR)
                p_sig = synth_piano_note(hz(note), duration=5.0, vel=0.75 - p_i * 0.08)
                p_end = min(total_n, idx + p_off + len(p_sig))
                if p_end > idx + p_off:
                    mix[idx + p_off:p_end] += p_sig[:p_end - (idx + p_off)]
                    
    stereo = apply_lush_studio_reverb(mix, decay_s=2.9, wet=0.44)
    save_master_track("tanhai_aesthetic_piano_violin_rain.wav", stereo)


# ─────────────────────────────────────────────────────────────
# 4. TRACK: rula_dene_wala_sarangi_bansuri.wav (ULTIMATE TEAR-JERKER)
# ─────────────────────────────────────────────────────────────
def build_rula_dene_wala_track():
    print("💔 Generating: rula_dene_wala_sarangi_bansuri.wav (Sarangi + Flute + Slow Drums)...")
    total_n = int(SR * DUR)
    mix = np.zeros(total_n)
    
    mix += synth_rain_and_sub_drone(DUR)
    
    sad_prog = [
        [45, 52, 57, 60],  # Am
        [41, 48, 53, 57],  # F
        [43, 50, 55, 58],  # Gm
        [40, 47, 52, 55],  # Em
    ]
    chord_dur = 4.8
    for loop in range(int(DUR / (chord_dur * len(sad_prog))) + 1):
        for c_i, chord in enumerate(sad_prog):
            start_t = (loop * len(sad_prog) + c_i) * chord_dur
            if start_t >= DUR - 2:
                break
            idx = int(start_t * SR)
            str_sig = synth_string_chord(chord, duration=6.0, vel=0.52)
            end_s = min(total_n, idx + len(str_sig))
            mix[idx:end_s] += str_sig[:end_s - idx]
            
    # Slow 56 BPM Deep Heartbeat
    cur_beat = 1.8
    kick = synth_soft_drum_kick()
    while cur_beat < DUR - 3:
        idx = int(cur_beat * SR)
        k_end = min(total_n, idx + len(kick))
        mix[idx:k_end] += kick[:k_end - idx] * 0.8
        cur_beat += 2.4

    # High Bansuri Lament
    flute_lament = [
        [(72, 3.5), (69, 3.0), (67, 3.2), (65, 4.5)],
        [(67, 2.8), (65, 3.0), (64, 2.5), (60, 5.0)],
        [(65, 3.2), (69, 3.5), (72, 4.0), (71, 4.5)],
    ]
    cur_f_t = 3.2
    while cur_f_t < DUR - 6:
        phrase = flute_lament[np.random.randint(0, len(flute_lament))]
        for note, ndur in phrase:
            idx = int(cur_f_t * SR)
            f_sig = synth_flute_note(hz(note), ndur, vel=0.8)
            end_f = min(total_n, idx + len(f_sig))
            if end_f > idx:
                mix[idx:end_f] += f_sig[:end_f - idx]
            cur_f_t += ndur * 0.86
        cur_f_t += 2.5

    stereo = apply_lush_studio_reverb(mix, decay_s=3.2, wet=0.48)
    save_master_track("rula_dene_wala_sarangi_bansuri.wav", stereo)


def save_master_track(filename: str, stereo_data: np.ndarray):
    path = os.path.join(OUT_DIR, filename)
    peak = np.max(np.abs(stereo_data))
    if peak > 0:
        stereo_data = stereo_data / peak * 0.80  # Mastered to -16 LUFS
    int_data = (stereo_data * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(int_data.tobytes())
    print(f"✅ Generated Viral Studio Track: {path} ({os.path.getsize(path) / 1024 / 1024:.1f} MB)")


def main():
    print("🔥 BUILDING 4 TIKTOK/REELS VIRAL MULTI-INSTRUMENT SAD TRACKS...")
    build_signature_viral_track()
    build_jaun_elia_darbari_track()
    build_tanhai_aesthetic_piano()
    build_rula_dene_wala_track()
    print("🎉 ALL 4 VIRAL MULTI-INSTRUMENT MASTER TRACKS READY IN assets/music/!")


if __name__ == "__main__":
    main()
