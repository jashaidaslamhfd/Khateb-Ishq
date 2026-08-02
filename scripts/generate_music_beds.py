#!/usr/bin/env python3
"""Generate CINEMATIC, EMOTIONAL sad music beds for Khateb-Ishq.

Previous version: simple sine-wave pads + basic piano = flat, boring.
This version: RICH orchestral textures — violin, cello, strings section,
reverb, emotional arcs, dynamic swells, Pakistani sad raag feel.

Every sample is synthesized note-by-note with numpy — 100% original,
no external audio, no samples, no attribution needed.

Usage:  python scripts/generate_music_beds.py
Output: assets/music/barish_violin.wav      (rain + violin + cello + strings)
        assets/music/tanhai_strings.wav      (sweeping strings + piano + reverb)
        assets/music/raat_cello.wav          (deep cello + distant violin + drone)
        assets/music/dard_sitar.wav          (sitar-style + tabla pulse + pads)
        assets/music/gham_violin.wav         (solo violin + emotional arc + rain)
Format: WAV, 44100 Hz, stereo, 16-bit — full quality for music-first videos
"""

import os
import wave

import numpy as np

SR = 22050           # 22050 for music beds (under voice); 44100 for music-first videos
DUR = 95.0           # seconds — 1.5 min per owner request
OUT_DIR = os.path.join("assets", "music")


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


# ═══════════════════════════════════════════════════════════════════════════
# CORE SYNTHESIS — Rich, cinematic voices
# ═══════════════════════════════════════════════════════════════════════════

def _fade_env(n: int, attack_s: float, release_s: float) -> np.ndarray:
    """Smooth fade-in/out envelope."""
    env = np.ones(n)
    a = min(int(SR * attack_s), n // 2)
    r = min(int(SR * release_s), n // 2)
    if a > 0:
        env[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 0:
        env[-r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return env


def violin_note(midi: int, dur: float, vel: float = 1.0, vibrato_rate: float = 5.5,
                vibrato_depth: float = 0.008, expressiveness: float = 0.15) -> np.ndarray:
    """Emotional violin voice with vibrato, bow attack, and harmonic richness.
    
    This is the heart of the cinematic sound — vibrato gives life,
    multiple partials give body, and the bow attack gives realism.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    
    # Vibrato — slow, emotional, like a real violinist
    vibrato = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    # Add slight vibrato delay (real violinists don't vibrate instantly)
    vib_attack = min(int(SR * 0.15), n)
    vibrato[:vib_attack] = 1.0 + vibrato_depth * 0.3 * np.sin(2 * np.pi * vibrato_rate * t[:vib_attack])
    
    phase = 2 * np.pi * f * np.cumsum(vibrato) / SR
    
    # Rich harmonics — violin has strong odd + even partials
    sig = (1.0 * np.sin(phase) +                    # fundamental
           0.45 * np.sin(2 * phase) +               # 2nd harmonic (bright)
           0.25 * np.sin(3 * phase) +               # 3rd harmonic (nasal)
           0.12 * np.sin(4 * phase) +               # 4th harmonic
           0.06 * np.sin(5 * phase) +               # 5th harmonic (air)
           0.03 * np.sin(6 * phase))                # 6th harmonic (shimmer)
    
    # Bow attack — quick ramp up (like a real bow on string)
    bow_attack = min(int(SR * 0.035), n)
    if bow_attack > 0:
        sig[:bow_attack] *= np.linspace(0, 1, bow_attack) ** 0.7
    
    # Bow release — slight lift
    bow_release = min(int(SR * 0.08), n)
    if bow_release > 0:
        sig[-bow_release:] *= np.linspace(1, 0.3, bow_release)
    
    # Expressive amplitude variation — real violinists breathe
    amp_mod = 1.0 + expressiveness * np.sin(2 * np.pi * 0.3 * t + np.random.uniform(0, 2*np.pi))
    
    # Decay envelope — long, singing decay
    env = np.exp(-t / (dur * 1.2))
    
    return (sig * env * amp_mod * vel).astype(np.float64) / 2.0


def cello_note(midi: int, dur: float, vel: float = 1.0, vibrato_rate: float = 4.0,
               vibrato_depth: float = 0.006) -> np.ndarray:
    """Deep, warm cello voice — the emotional anchor of sad music.
    
    Lower register, slower vibrato, richer low harmonics.
    """
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    
    # Slower, deeper vibrato than violin
    vibrato = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    vib_attack = min(int(SR * 0.2), n)
    vibrato[:vib_attack] = 1.0 + vibrato_depth * 0.2 * np.sin(2 * np.pi * vibrato_rate * t[:vib_attack])
    
    phase = 2 * np.pi * f * np.cumsum(vibrato) / SR
    
    # Cello: strong fundamental + warm overtones
    sig = (1.0 * np.sin(phase) +
           0.35 * np.sin(2 * phase) +
           0.18 * np.sin(3 * phase) +
           0.08 * np.sin(4 * phase) +
           0.15 * np.sin(0.5 * phase))    # sub-octave warmth
    
    # Slower bow attack than violin
    bow_attack = min(int(SR * 0.06), n)
    if bow_attack > 0:
        sig[:bow_attack] *= np.linspace(0, 1, bow_attack) ** 0.5
    
    # Long singing decay
    env = np.exp(-t / (dur * 1.5))
    
    return (sig * env * vel).astype(np.float64) / 1.8


def strings_pad(midis, dur: float, gain: float = 1.0, detune: float = 0.003) -> np.ndarray:
    """Lush string section pad — detuned voices for thickness (fast vectorized)."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    left, right = np.zeros(n), np.zeros(n)
    
    for m in midis:
        f = hz(m)
        for voice in range(3):
            det = 1.0 + np.random.uniform(-detune, detune)
            # Simple vibrato (no cumsum — much faster)
            vib_rate = 4.0 + np.random.uniform(-1, 1)
            vib_depth = 0.003 + np.random.uniform(-0.001, 0.001)
            freq_mod = f * det * (1.0 + vib_depth * np.sin(2 * np.pi * vib_rate * t))
            phase = 2 * np.pi * np.cumsum(freq_mod) / SR
            
            voice_sig = (np.sin(phase) +
                        0.3 * np.sin(2 * phase) +
                        0.12 * np.sin(3 * phase))
            
            pan = np.random.uniform(-0.3, 0.3)
            left += voice_sig * (1.0 - pan)
            right += voice_sig * (1.0 + pan)
    
    env = _fade_env(n, min(2.0, dur * 0.3), min(2.5, dur * 0.4))
    return np.stack([left * env, right * env]) * gain / (1.5 * len(midis) * 3)


def piano_note(midi: int, dur: float, vel: float = 1.0) -> np.ndarray:
    """Soft felt-piano voice with rich harmonics and long decay."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = (np.sin(2 * np.pi * f * t) +
           0.55 * np.sin(2 * np.pi * 2 * f * t) +
           0.22 * np.sin(2 * np.pi * 3 * f * t) +
           0.08 * np.sin(2 * np.pi * 4 * f * t))
    attack = max(2, int(SR * 0.004))
    env = np.exp(-t / (dur * 0.34))
    env[:attack] = np.linspace(0, 1, attack)
    return (sig * env * vel).astype(np.float64) / 1.85


def bass_note(midi: int, dur: float, vel: float = 1.0) -> np.ndarray:
    """Deep bass foundation."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 0.5 * f * t)
    env = _fade_env(n, 0.25, min(1.0, dur * 0.4))
    return sig * env * vel / 1.25


# ═══════════════════════════════════════════════════════════════════════════
# AMBIENCE LAYERS — Rain, thunder, crackle, wind
# ═══════════════════════════════════════════════════════════════════════════

def rain_layer(n: int, gain: float, intensity: float = 1.0) -> np.ndarray:
    """Realistic rain — filtered noise with slow amplitude wander."""
    if gain <= 0:
        return np.zeros((2, n))
    rng = np.random.default_rng(42)
    noise = rng.standard_normal((2, n))
    # Low-pass filter (simple moving average)
    k = np.hanning(401)
    k /= k.sum()
    out_l = np.convolve(noise[0], k, mode="same")
    out_r = np.convolve(noise[1], k, mode="same")
    # Slow amplitude modulation (rain intensity varies)
    mod = np.convolve(rng.standard_normal(n), np.hanning(int(SR * 2)), mode="same")
    mod /= np.abs(mod).max() + 1e-9
    lfo = 0.55 + 0.45 * mod
    return np.stack([out_l * lfo, out_r * lfo]) * gain * intensity * 6.0


def thunder_rumble(n: int, gain: float = 0.08) -> np.ndarray:
    """Distant thunder rumbles — low-frequency bursts."""
    if gain <= 0:
        return np.zeros((2, n))
    rng = np.random.default_rng(77)
    out = np.zeros((2, n))
    # 2-3 rumbles per minute
    num_rumbles = max(1, int(n / SR / 30))
    for _ in range(num_rumbles):
        pos = int(rng.uniform(SR * 5, n - SR * 5))
        dur = rng.uniform(1.5, 4.0)
        length = int(SR * dur)
        if pos + length > n:
            continue
        t = np.arange(length) / SR
        # Low-frequency rumble
        freq = rng.uniform(30, 60)
        rumble = np.sin(2 * np.pi * freq * t) * np.exp(-t / (dur * 0.5))
        # Add some noise
        noise = rng.standard_normal(length) * 0.3
        k = np.hanning(201)
        k /= k.sum()
        noise = np.convolve(noise, k, mode="same")
        burst = rumble + noise
        env = _fade_env(length, 0.5, min(1.5, dur * 0.5))
        burst *= env
        out[0, pos:pos+length] += burst * gain
        out[1, pos:pos+length] += burst * gain * 0.9  # slight stereo offset
    return out


def crackle_layer(n: int, gain: float) -> np.ndarray:
    """Vinyl crackle / fireplace crackle."""
    if gain <= 0:
        return np.zeros((2, n))
    rng = np.random.default_rng(88)
    out = np.zeros((2, n))
    hits = int(n / SR * 6.5)
    for _ in range(hits):
        pos = int(rng.uniform(0, n - int(SR * 0.004)))
        ln = int(SR * rng.uniform(0.0005, 0.003))
        if pos + ln > n:
            continue
        burst = rng.uniform(-1, 1, ln) * np.linspace(1, 0, ln)
        out[0, pos:pos+ln] += burst * gain
        out[1, pos:pos+ln] += burst * gain * 0.8
    return out * 0.9


# ═══════════════════════════════════════════════════════════════════════════
# REVERB — Simple convolution-style reverb for depth
# ═══════════════════════════════════════════════════════════════════════════

def simple_reverb(sig: np.ndarray, wet: float = 0.25, decay: float = 0.4,
                  delays_ms: list = [23, 37, 53, 71, 89, 113]) -> np.ndarray:
    """Simple multi-tap delay reverb — adds depth and space.
    
    This is what makes the difference between "dry/flat" and "cinematic/wide".
    """
    is_stereo = sig.ndim == 2
    out = sig.copy()
    
    for delay_ms in delays_ms:
        offset = int(SR * delay_ms / 1000.0)
        gain = wet * (decay ** (delay_ms / 30.0))
        if is_stereo:
            if offset < sig.shape[1]:
                out[:, offset:] += sig[:, :-offset] * gain
        else:
            if offset < len(sig):
                out[offset:] += sig[:-offset] * gain
    
    return out


# ═══════════════════════════════════════════════════════════════════════════
# CHORD PROGRESSIONS — Sad, emotional, Pakistani raag-inspired
# ═══════════════════════════════════════════════════════════════════════════

# Minor key progressions that evoke deep sadness
Gm  = [55, 58, 62, 65]   # G minor
Eb  = [51, 55, 58, 63]   # Eb major
Bb  = [46, 50, 53, 58]   # Bb major
F   = [41, 45, 48, 53]   # F major
Am  = [45, 48, 52, 57]   # A minor
C   = [48, 52, 55, 60]   # C major
Em  = [40, 47, 52, 55]   # E minor
Dm  = [50, 53, 57, 62]   # D minor
Bm  = [47, 50, 54, 59]   # B minor
D   = [50, 54, 57, 62]   # D major
G   = [43, 47, 50, 55]   # G major
Fm  = [41, 44, 48, 53]   # F minor
Cm  = [48, 51, 55, 60]   # C minor
Ab  = [44, 48, 51, 56]   # Ab major
Bbm = [46, 49, 53, 58]   # Bb minor

# Pentatonic scales for melody
GM_PENT = [55, 58, 60, 62, 65, 67, 70, 72, 74, 77]
AM_PENT = [57, 60, 62, 64, 69, 72, 74, 76, 81]
EM_PENT = [52, 55, 57, 59, 64, 67, 69, 71, 76]
DM_PENT = [50, 53, 55, 57, 62, 65, 67, 69, 74]
BM_PENT = [47, 50, 52, 54, 59, 62, 64, 66, 71]


# ═══════════════════════════════════════════════════════════════════════════
# MELODY GENERATOR — Emotional, structured, not random
# ═══════════════════════════════════════════════════════════════════════════

def generate_violin_melody(scale: list, root: int, bpm: float, total_bars: int,
                           intro_s: float, seed: int) -> list:
    """Generate a structured, emotional violin melody with AABA phrasing.
    
    This isn't random notes — it follows musical phrase structure:
    A: main theme (sad, descending)
    A: repeat with slight variation
    B: bridge (tension, ascending)
    A: return to theme (resolution)
    """
    rng = np.random.RandomState(seed)
    spb = 60.0 / bpm
    bar_s = 4 * spb
    notes = []
    idx = len(scale) // 2  # Start in middle of scale
    
    # Phrase patterns (slot_eighths, duration_eighths)
    sad_patterns = [
        [(0, 6), (6, 2), (8, 4), (12, 4)],       # Long-short, long-long
        [(0, 4), (4, 4), (8, 2), (10, 2), (12, 4)],  # Even, then two shorts
        [(0, 8), (8, 8)],                           # Two long held notes
        [(0, 2), (2, 2), (4, 4), (8, 4), (12, 4)],   # Quick start, then long
        [(0, 4), (4, 2), (6, 2), (8, 8)],           # Classic sad descent
    ]
    bridge_patterns = [
        [(0, 2), (2, 2), (4, 2), (6, 2), (8, 4), (12, 4)],  # Urgent, then resolve
        [(0, 4), (4, 4), (8, 2), (10, 2), (12, 2), (14, 2)],  # Building tension
    ]
    
    for bar in range(total_bars):
        # AABA structure
        phrase = bar // 4
        bar_in_phrase = bar % 4
        
        if phrase % 2 == 1 and bar_in_phrase < 2:
            # B section (bridge) — more tension
            pattern = bridge_patterns[bar_in_phrase % len(bridge_patterns)]
            step_bias = 1  # Ascending tendency in bridge
        else:
            # A section — sad, descending
            pattern = sad_patterns[bar_in_phrase % len(sad_patterns)]
            step_bias = -1  # Descending tendency in A section
        
        is_last = bar >= total_bars - 2
        if is_last:
            pattern = [(0, 16)]  # Final long resolution note
        
        # Sometimes skip a bar for breathing space (silence = emotion)
        if not is_last and rng.random() < 0.15:
            continue
        
        for slot_e, len_e in pattern:
            t0 = intro_s + bar * bar_s + slot_e / 2 * spb
            dur = max(0.9 * (len_e / 2) * spb, 0.3)
            
            if is_last:
                # Resolve to root (octave up for emotional impact)
                midi = root + 12
                vel = 0.85
            else:
                # Melodic movement — stepwise with occasional leaps
                step = rng.choice([-2, -1, -1, step_bias, step_bias, 2])
                idx = max(1, min(len(scale) - 2, idx + step))
                midi = scale[idx]
                vel = 0.55 + 0.35 * rng.random()
                # Emphasize downbeats
                if slot_e == 0:
                    vel = min(1.0, vel + 0.15)
            
            notes.append((t0, min(dur, 3.5), midi, vel))
    
    return notes


def generate_cello_counter_melody(melody_notes: list, root: int, bpm: float,
                                   seed: int) -> list:
    """Generate a cello counter-melody that supports the violin.
    
    The cello plays slower, longer notes — typically the root or 5th
    of whatever the violin is playing. This creates harmonic depth.
    """
    rng = np.random.RandomState(seed + 1000)
    notes = []
    spb = 60.0 / bpm
    bar_s = 4 * spb
    
    # Place cello notes every 2-4 bars
    t = 4.0  # start after intro
    while t < DUR - 8.0:
        dur = rng.uniform(3.0, 6.0)
        # Find closest violin note to harmonize with
        violin_pitch = root
        for vn_t, vn_d, vn_m, vn_v in melody_notes:
            if abs(vn_t - t) < 2.0:
                violin_pitch = vn_m
                break
        
        # Cello plays root or 5th below violin
        cello_options = [root - 12, root - 7, root - 5, violin_pitch - 12, violin_pitch - 7]
        midi = rng.choice(cello_options)
        vel = 0.4 + 0.2 * rng.random()
        
        notes.append((t, min(dur, 6.0), midi, vel))
        t += rng.uniform(4.0, 8.0)
    
    return notes


# ═══════════════════════════════════════════════════════════════════════════
# ARRANGEMENT — Build complete tracks
# ═══════════════════════════════════════════════════════════════════════════

def _place_notes(notes: list, total_n: int, voice_fn, **kwargs) -> np.ndarray:
    """Place a list of (t0, dur, midi, vel) notes into a stereo buffer."""
    left = np.zeros(total_n)
    right = np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = voice_fn(midi, dur, vel, **kwargs) if 'vibrato_rate' in voice_fn.__code__.co_varnames else voice_fn(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n - idx)
        if L > 0:
            # Slight stereo spread
            left[idx:idx+L] += sig[:L] * 0.55
            right[idx:idx+L] += sig[:L] * 0.45
    return np.stack([left, right])


def _place_violin(notes: list, total_n: int) -> np.ndarray:
    """Place violin notes with vibrato."""
    left = np.zeros(total_n)
    right = np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = violin_note(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n)
        if L > 0:
            left[idx:idx+L] += sig[:L] * 0.55
            right[idx:idx+L] += sig[:L] * 0.45
    return np.stack([left, right])


def _place_cello(notes: list, total_n: int) -> np.ndarray:
    """Place cello notes."""
    left = np.zeros(total_n)
    right = np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = cello_note(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n)
        if L > 0:
            left[idx:idx+L] += sig[:L] * 0.5
            right[idx:idx+L] += sig[:L] * 0.5
    return np.stack([left, right])


def _place_piano(notes: list, total_n: int) -> np.ndarray:
    """Place piano notes."""
    left = np.zeros(total_n)
    right = np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = piano_note(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n)
        if L > 0:
            left[idx:idx+L] += sig[:L] * 0.52
            right[idx:idx+L] += sig[:L] * 0.48
    return np.stack([left, right])


def _place_bass(notes: list, total_n: int) -> np.ndarray:
    """Place bass notes (centered)."""
    out = np.zeros(total_n)
    for t0, dur, midi, vel in notes:
        sig = bass_note(midi, dur, vel)
        idx = int(t0 * SR)
        L = min(len(sig), total_n - idx)
        if L > 0:
            out[idx:idx+L] += sig[:L]
    return np.stack([out * 0.5, out * 0.5])


def progression(chords, chord_s: float = 12.0, cross: float = 2.0, vol: float = 1.0) -> np.ndarray:
    """Build a string section chord progression across the whole track."""
    n = int(SR * DUR)
    out = np.zeros((2, n))
    start = 0.0
    seglen = chord_s + cross
    for ch in chords:
        seg = strings_pad(ch, seglen, gain=vol, detune=0.004)
        idx = int(start * SR)
        L = min(seg.shape[1], n - idx)
        if L > 0:
            out[:, idx:idx+L] += seg[:, :L]
        start += chord_s
        if start >= DUR:
            break
    return out


def _dynamic_swell(n: int, peak_at: float = 0.6, depth: float = 0.3) -> np.ndarray:
    """Create a slow volume swell that builds and releases emotion.
    
    This is what makes music feel CINEMATIC — it breathes.
    """
    t = np.arange(n) / SR
    total_s = n / SR
    # Slow sine-based swell (multiple overlapping periods)
    swell = 1.0 + depth * (
        0.5 * np.sin(2 * np.pi * t / total_s * 1.0 - np.pi/2) +
        0.3 * np.sin(2 * np.pi * t / total_s * 2.0 - np.pi/2) +
        0.2 * np.sin(2 * np.pi * t / total_s * 0.5 - np.pi/2)
    )
    return np.clip(swell, 0.4, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# TRACK BUILDERS — Each one is a unique cinematic composition
# ═══════════════════════════════════════════════════════════════════════════

def build_barish_violin():
    """🌧️ Rain + Solo Violin + Cello + Strings — The signature sad track.
    
    Pakistani sad raag feel: slow, expressive violin over rain with
    deep cello foundation and lush string pads.
    """
    np.random.seed(101)
    n = int(SR * DUR)
    bpm = 52
    root = 57  # A minor
    intro_s = 5.0
    
    # String pad progression (Am - F - C - Em)
    pads = progression([Am, F, C, Em], chord_s=10.0, vol=0.8)
    
    # Violin melody — emotional, structured
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_violin_melody(AM_PENT, root, bpm, total_bars, intro_s, seed=101)
    violin = _place_violin(melody, n)
    
    # Cello counter-melody
    cello_melody = generate_cello_counter_melody(melody, root, bpm, seed=101)
    cello = _place_cello(cello_melody, n)
    
    # Sparse piano accents
    rng = np.random.RandomState(101)
    piano_notes = []
    t = intro_s + 2.0
    while t < DUR - 8.0:
        midi = rng.choice([root, root+3, root+7, root+12])
        piano_notes.append((t, rng.uniform(1.5, 3.0), midi, 0.3))
        t += rng.uniform(5.0, 10.0)
    piano = _place_piano(piano_notes, n)
    
    # Bass
    bass_notes = []
    for chord, t0 in [(Am, intro_s), (F, intro_s+10), (C, intro_s+20), (Em, intro_s+30)]:
        bass_notes.append((t0, 8.0, chord[0] - 12, 0.4))
    bass = _place_bass(bass_notes, n)
    
    # Rain + thunder
    rain = rain_layer(n, 0.035, intensity=1.2)
    thunder = thunder_rumble(n, 0.06)
    
    # Dynamic swell
    swell_l = _dynamic_swell(n, depth=0.25)
    swell_r = _dynamic_swell(n, depth=0.25)
    
    # Mix
    mix = (pads + violin * 1.8 + cello * 1.4 + piano * 0.8 + bass * 0.6 + 
           rain + thunder + crackle_layer(n, 0.012))
    mix[0] *= swell_l
    mix[1] *= swell_r
    
    # Apply reverb
    mix = simple_reverb(mix, wet=0.3, decay=0.35)
    
    return master(mix, "barish_violin.wav")


def build_tanhai_strings():
    """🎻 Lush Strings + Piano + Emotional Arc — The weeping strings track.
    
    No rain — just pure emotional strings swelling and receding,
    with lonely piano notes in the silence.
    """
    np.random.seed(202)
    n = int(SR * DUR)
    bpm = 54
    root = 52  # E minor
    intro_s = 5.0
    
    # String pad progression (Em - C - G - Am) — more dramatic
    pads = progression([Em, C, G, Am], chord_s=10.0, vol=1.0)
    
    # Second string layer — higher, thinner (violins)
    pads_high = progression([[m+12 for m in ch] for ch in [Em, C, G, Am]], 
                           chord_s=10.0, vol=0.4)
    
    # Violin melody
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_violin_melody(EM_PENT, root, bpm, total_bars, intro_s, seed=202)
    violin = _place_violin(melody, n)
    
    # Cello
    cello_melody = generate_cello_counter_melody(melody, root, bpm, seed=202)
    cello = _place_cello(cello_melody, n)
    
    # Sparse piano — more present
    rng = np.random.RandomState(202)
    piano_notes = []
    t = intro_s
    while t < DUR - 8.0:
        midi = rng.choice([root, root+3, root+5, root+7, root+12, root+15])
        piano_notes.append((t, rng.uniform(2.0, 4.0), midi, 0.45))
        t += rng.uniform(3.0, 7.0)
    piano = _place_piano(piano_notes, n)
    
    # Bass
    bass_notes = []
    for chord, t0 in [(Em, intro_s), (C, intro_s+10), (G, intro_s+20), (Am, intro_s+30)]:
        bass_notes.append((t0, 8.0, chord[0] - 12, 0.5))
    bass = _place_bass(bass_notes, n)
    
    # Crackling fire
    crackle = crackle_layer(n, 0.018)
    
    # Dynamic swell — bigger for this track
    swell_l = _dynamic_swell(n, depth=0.35)
    swell_r = _dynamic_swell(n, depth=0.35)
    
    # Mix
    mix = (pads + pads_high + violin * 1.6 + cello * 1.2 + piano * 1.0 + 
           bass * 0.5 + crackle)
    mix[0] *= swell_l
    mix[1] *= swell_r
    
    # Apply reverb (more for this spacious track)
    mix = simple_reverb(mix, wet=0.35, decay=0.4)
    
    return master(mix, "tanhai_strings.wav")


def build_raat_cello():
    """🌙 Deep Cello + Distant Violin + Drone — The night meditation track.
    
    Slow, deep, meditative. The cello is the lead voice here,
    with a distant violin echoing like a memory.
    """
    np.random.seed(303)
    n = int(SR * DUR)
    bpm = 48
    root = 52  # E minor
    intro_s = 6.0
    
    # Drone pad — sustained, barely moving
    t = np.arange(n) / SR
    drone_l = np.zeros(n)
    drone_r = np.zeros(n)
    for m in Em:
        f = hz(m)
        drone_l += np.sin(2 * np.pi * f * 0.999 * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
        drone_r += np.sin(2 * np.pi * f * 1.001 * t) + 0.3 * np.sin(2 * np.pi * 2.002 * f * t)
    drone_env = _fade_env(n, 6.0, 6.0)
    drone = np.stack([drone_l * drone_env, drone_r * drone_env]) * 0.6
    
    # Slow pad progression
    pads = progression([Em, C, G, Am], chord_s=14.0, vol=0.5)
    
    # Cello melody — the main voice
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_violin_melody(EM_PENT, root, bpm, total_bars, intro_s, seed=303)
    # Shift melody down an octave for cello
    cello_melody = [(t0, dur*1.5, midi-12, vel*0.9) for t0, dur, midi, vel in melody]
    cello = _place_cello(cello_melody, n)
    
    # Distant violin echo (play same melody but delayed and quieter)
    violin_melody = [(t0+3.0, dur*0.8, midi+12, vel*0.3) for t0, dur, midi, vel in melody]
    violin = _place_violin(violin_melody, n)
    
    # Very sparse piano
    rng = np.random.RandomState(303)
    piano_notes = []
    t = intro_s + 5.0
    while t < DUR - 10.0:
        midi = rng.choice([root, root+7, root+12])
        piano_notes.append((t, rng.uniform(2.0, 4.0), midi, 0.2))
        t += rng.uniform(8.0, 14.0)
    piano = _place_piano(piano_notes, n)
    
    # Very faint rain
    rain = rain_layer(n, 0.012, intensity=0.5)
    
    # Dynamic swell — gentle
    swell_l = _dynamic_swell(n, depth=0.2)
    swell_r = _dynamic_swell(n, depth=0.2)
    
    # Mix
    mix = (drone + pads + cello * 2.0 + violin * 0.8 + piano * 0.6 + rain)
    mix[0] *= swell_l
    mix[1] *= swell_r
    
    # Heavy reverb for spaciousness
    mix = simple_reverb(mix, wet=0.4, decay=0.45)
    
    return master(mix, "raat_cello.wav")


def build_dard_sitar():
    """🪕 Sitar-style + Pads + Drone — The Pakistani sad raag track.
    
    Plucked string sounds (sitar-like) with slow drone and
    emotional pads. This is the most "desi" of all tracks.
    """
    np.random.seed(404)
    n = int(SR * DUR)
    bpm = 50
    root = 50  # D minor
    intro_s = 5.0
    
    # Pad progression (Dm - Bb - F - C)
    pads = progression([Dm, Bb, F, C], chord_s=11.0, vol=0.7)
    
    # Sitar-style melody (using pluck_note-style synthesis)
    rng = np.random.RandomState(404)
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    sitar_notes = []
    idx = len(DM_PENT) // 2
    for bar in range(total_bars):
        is_last = bar >= total_bars - 2
        if not is_last and rng.random() < 0.2:
            continue
        for slot_e in [0, 4, 8, 12]:
            if rng.random() < 0.4:
                continue
            t0 = intro_s + bar * (4 * 60.0/bpm) + slot_e/2 * (60.0/bpm)
            dur = rng.uniform(0.5, 2.0)
            if is_last:
                midi = root + 12
            else:
                step = rng.choice([-2, -1, -1, 1, 1, 2])
                idx = max(1, min(len(DM_PENT)-2, idx + step))
                midi = DM_PENT[idx]
            vel = 0.5 + 0.3 * rng.random()
            sitar_notes.append((t0, dur, midi, vel))
    
    # Generate sitar-style notes (Karplus-Strong)
    sitar_l = np.zeros(n)
    sitar_r = np.zeros(n)
    for t0, dur, midi, vel in sitar_notes:
        # Karplus-Strong synthesis
        f = hz(midi)
        buf_len = max(4, int(SR / f))
        buf = rng.uniform(-1, 1, buf_len)
        note_len = int(SR * dur)
        out = np.empty(note_len)
        idx_k = 0
        for i in range(note_len):
            cur = buf[idx_k]
            nxt = buf[(idx_k + 1) % buf_len]
            new = 0.994 * 0.5 * (cur + nxt) + 0.003 * np.sin(2 * np.pi * 3.01 * i / SR)  # sympathetic resonance
            buf[idx_k] = new
            out[i] = cur
            idx_k = (idx_k + 1) % buf_len
        # Add some brightness
        out += 0.2 * np.sin(2 * np.pi * f * 2 * np.arange(note_len) / SR) * np.exp(-np.arange(note_len) / SR / (dur * 0.3))
        attack = max(2, int(SR * 0.003))
        out[:attack] *= np.linspace(0, 1, attack)
        out *= vel * 0.6
        
        start = int(t0 * SR)
        L = min(note_len, n - start)
        if L > 0:
            sitar_l[start:start+L] += out[:L] * 0.55
            sitar_r[start:start+L] += out[:L] * 0.45
    
    sitar = np.stack([sitar_l, sitar_r])
    
    # Cello drone
    cello_drone = np.zeros((2, n))
    for m in [root - 12, root - 5]:
        sig = cello_note(m, DUR, 0.3)
        cello_drone[0] += sig * 0.5
        cello_drone[1] += sig * 0.5
    
    # Faint rain
    rain = rain_layer(n, 0.01, intensity=0.3)
    
    # Dynamic swell
    swell_l = _dynamic_swell(n, depth=0.2)
    swell_r = _dynamic_swell(n, depth=0.2)
    
    # Mix
    mix = (pads + sitar * 1.5 + cello_drone + rain)
    mix[0] *= swell_l
    mix[1] *= swell_r
    
    # Reverb
    mix = simple_reverb(mix, wet=0.3, decay=0.35)
    
    return master(mix, "dard_sitar.wav")


def build_gham_violin():
    """💔 Solo Violin + Emotional Arc + Rain — The most emotional track.
    
    Pure violin with deep emotional arc — starts soft, builds to
    a crying peak, then resolves to silence. This is the one that
    makes people cry.
    """
    np.random.seed(505)
    n = int(SR * DUR)
    bpm = 50
    root = 55  # G minor
    intro_s = 5.0
    
    # Pad progression (Gm - Eb - Bb - F) — the saddest progression
    pads = progression([Gm, Eb, Bb, F], chord_s=10.0, vol=0.6)
    
    # Violin melody — the most emotional one
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    melody = generate_violin_melody(GM_PENT, root, bpm, total_bars, intro_s, seed=505)
    violin = _place_violin(melody, n)
    
    # Cello counter-melody
    cello_melody = generate_cello_counter_melody(melody, root, bpm, seed=505)
    cello = _place_cello(cello_melody, n)
    
    # High violin (octave up) for emotional peak
    high_melody = [(t0, dur*0.7, midi+12, vel*0.4) for t0, dur, midi, vel in melody 
                   if t0 > DUR * 0.4 and t0 < DUR * 0.7]  # Only in middle section
    high_violin = _place_violin(high_melody, n)
    
    # Sparse piano
    rng = np.random.RandomState(505)
    piano_notes = []
    t = intro_s + 3.0
    while t < DUR - 8.0:
        midi = rng.choice([root, root+3, root+7, root+10, root+12])
        piano_notes.append((t, rng.uniform(2.0, 4.0), midi, 0.35))
        t += rng.uniform(4.0, 8.0)
    piano = _place_piano(piano_notes, n)
    
    # Bass
    bass_notes = []
    for chord, t0 in [(Gm, intro_s), (Eb, intro_s+10), (Bb, intro_s+20), (F, intro_s+30)]:
        bass_notes.append((t0, 8.0, chord[0] - 12, 0.45))
    bass = _place_bass(bass_notes, n)
    
    # Rain + thunder
    rain = rain_layer(n, 0.04, intensity=1.0)
    thunder = thunder_rumble(n, 0.05)
    
    # BIG emotional dynamic swell
    swell_l = _dynamic_swell(n, depth=0.4)
    swell_r = _dynamic_swell(n, depth=0.4)
    
    # Mix
    mix = (pads + violin * 2.0 + cello * 1.5 + high_violin * 1.2 + 
           piano * 0.9 + bass * 0.6 + rain + thunder + crackle_layer(n, 0.010))
    mix[0] *= swell_l
    mix[1] *= swell_r
    
    # Heavy reverb for maximum emotion
    mix = simple_reverb(mix, wet=0.35, decay=0.4)
    
    return master(mix, "gham_violin.wav")


# ═══════════════════════════════════════════════════════════════════════════
# MASTER — Final processing and write
# ═══════════════════════════════════════════════════════════════════════════

def master(sig: np.ndarray, name: str) -> str:
    """Soft-limit, fade in/out, normalize, write 16-bit stereo WAV."""
    # Soft limiting (tanh saturation)
    sig = np.tanh(sig * 1.1)
    
    # Fade in/out
    f = int(SR * 3.0)
    if sig.ndim == 2:
        sig[0, :f] *= np.linspace(0.0, 1.0, f)
        sig[0, -f:] *= np.linspace(1.0, 0.0, f)
        sig[1, :f] *= np.linspace(0.0, 1.0, f)
        sig[1, -f:] *= np.linspace(1.0, 0.0, f)
    else:
        sig[:f] *= np.linspace(0.0, 1.0, f)
        sig[-f:] *= np.linspace(1.0, 0.0, f)
    
    # Normalize to -3 dBFS
    peak = np.abs(sig).max() or 1.0
    pcm = (sig / peak * 0.70 * 32767).astype(np.int16)
    
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    
    # Write stereo WAV
    if pcm.ndim == 1:
        # Mono → stereo
        pcm = np.stack([pcm, pcm]).T
    elif pcm.ndim == 2:
        pcm = pcm.T
    
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    
    print(f"  wrote {path}  ({DUR:.0f}s, {os.path.getsize(path)//1024} KB)")
    return path


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def build_tiktok_viral():
    """🎵 TikTok Viral Sad Poetry Bed — The "Slowed + Reverb" formula.
    
    Formula: Deep Rain + Heavy Reverb + Simple Piano + Crying High Violin.
    This matches the specific "viral" sound people search for on TikTok/Shorts.
    """
    np.random.seed(606)
    n = int(SR * DUR)
    bpm = 42  # Very slow
    root = 50  # D minor
    intro_s = 4.0
    
    # Pad progression (Dm - Bb - Gm - A)
    pads = progression([Dm, Bb, Gm, A], chord_s=12.0, vol=0.55)
    
    # 1. SIMPLE PIANO HOOK (The "TikTok" style)
    # Slow, simple notes with long spaces
    rng = np.random.RandomState(606)
    piano_notes = []
    t = intro_s
    while t < DUR - 5.0:
        # High piano notes for that "chime" feel
        midi = rng.choice([root+12, root+15, root+17, root+22, root+24])
        piano_notes.append((t, rng.uniform(3.0, 5.0), midi, 0.4))
        t += rng.uniform(6.0, 10.0)
    piano = _place_piano(piano_notes, n)
    
    # 2. CRYING HIGH VIOLIN
    # Very high pitch, lots of vibrato
    total_bars = int((DUR - intro_s - 5.0) / (4 * 60.0 / bpm))
    v_melody = []
    t = intro_s + 2.0
    for _ in range(total_bars * 2):
        dur = rng.uniform(4.0, 8.0)
        midi = rng.choice([root+12, root+14, root+17, root+20])
        v_melody.append((t, dur, midi, 0.5))
        t += dur + rng.uniform(2.0, 5.0)
    violin = _place_violin(v_melody, n)
    
    # 3. ATMOSPHERE (Heavy Rain + Wind)
    rain = rain_layer(n, 0.06, intensity=1.2)
    # Muffled wind effect (low frequency noise)
    wind_noise = rng.standard_normal((2, n))
    k = np.hanning(2001)  # Heavy low pass
    k /= k.sum()
    wind = np.stack([np.convolve(wind_noise[0], k, mode="same"), 
                     np.convolve(wind_noise[1], k, mode="same")]) * 0.05
    
    # Mix
    mix = (pads + piano * 1.5 + violin * 1.8 + rain + wind)
    
    # 4. Muffled / Low-Pass Filter (The "next door" effect)
    # Simple moving average to cut highs
    k_lp = np.ones(8) / 8.0
    mix[0] = np.convolve(mix[0], k_lp, mode="same")
    mix[1] = np.convolve(mix[1], k_lp, mode="same")
    
    # 5. HEAVY REVERB (The "Slowed + Reverb" feel)
    mix = simple_reverb(mix, wet=0.55, decay=0.6)
    
    return master(mix, "tiktok_style_poetry.wav")


def main():
    print("🎻 Synthesizing CINEMATIC Khateb-Ishq music beds (numpy only, no samples)...")
    print("   Now with: violin, cello, lush strings, reverb, emotional arcs, thunder")
    print()
    paths = [
        build_barish_violin(),   # 🌧️ Rain + Violin + Cello
        build_tanhai_strings(),  # 🎻 Lush Strings + Piano
        build_raat_cello(),      # 🌙 Deep Cello + Drone
        build_dard_sitar(),      # 🪕 Sitar-style + Drone
        build_gham_violin(),     # 💔 Solo Violin + Emotional Arc
        build_tiktok_viral(),    # 🎵 TikTok Viral Style
    ]
    print(f"\n✅ Done — {len(paths)} CINEMATIC tracks in {OUT_DIR}/")
    print("   100% original: no attribution needed, no claim risk.")
    print("   Features: violin vibrato, cello counter-melody, string section,")
    print("   reverb, thunder, dynamic swells, AABA phrasing")


if __name__ == "__main__":
    main()
