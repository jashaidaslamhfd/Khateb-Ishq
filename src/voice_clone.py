#!/usr/bin/env python3
"""Owner's OWN cloned voice — zero-shot clone via Qwen3-TTS-12Hz-0.6B-Base.

Why this model (verified 2026-07-22):
  - Apache-2.0 license  -> monetization/commercial safe.
  - Zero-shot voice clone from a 3-30s reference  -> NO training step, so the
    whole pipeline stays 100% automated (no Colab, no manual work).
  - 0.6B params  -> runs on GitHub Actions' free CPU runners (~16 GB RAM).
  - Official language list is 10 major languages and Urdu is NOT among them,
    but the 12Hz tokenizer is acoustic and the LM consumes raw Urdu script —
    cross-lingual zero-shot cloning is therefore attempted with the reference
    transcript passed verbatim. FIRST RUN is a quality test: if the Urdu
    talaffuz is not mushaira-grade, _engine() falls back to Edge-TTS Asad.

Privacy: the owner's reference WAV is NOT committed raw to the public repo —
it ships as assets/voice_reference.wav.gpg (symmetric-encrypted) and the
workflow decrypts it at runtime using the VOICE_REF_PASSPHRASE secret.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
_REF_WAV = "assets/voice_reference.wav"

_model = None  # lazy singleton — loading 0.6B weights per scene would be absurd


def reference_ready() -> Optional[str]:
    """Path of the decrypted reference WAV if present, else None."""
    import os.path
    path = os.environ.get("VOICE_REFERENCE", _REF_WAV)
    return path if os.path.exists(path) and os.path.getsize(path) > 1000 else None


def _ref_text() -> str:
    """Verbatim transcript of the reference recording (guide ships the script,
    so the transcript is known exactly — zero-shot quality depends on it)."""
    txt_path = os.environ.get("VOICE_REFERENCE_TEXT", "assets/voice_reference.txt")
    if os.path.exists(txt_path):
        return open(txt_path, encoding="utf-8").read().strip()
    return os.environ.get("QWEN_CLONE_REF_TEXT", "")


def _load_model():
    global _model
    if _model is not None:
        return _model
    import torch
    from qwen_tts import Qwen3TTSModel
    name = os.environ.get("QWEN_CLONE_MODEL", DEFAULT_MODEL)
    logger.info("Loading voice-clone model %s on CPU (one-time per run)...", name)
    _model = Qwen3TTSModel.from_pretrained(
        name,
        device_map="cpu",
        dtype=torch.float32,          # bf16 is GPU-only; fp32 CPU is fine at 0.6B
    )
    logger.info("Voice-clone model ready.")
    return _model


def synth_clone(text: str, out_path: str) -> None:
    """Synthesize `text` in the owner's cloned voice -> writes WAV via soundfile."""
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel  # noqa: F401  (presence check)

    ref = reference_ready()
    if not ref:
        raise RuntimeError("Voice reference missing (VOICE_REFERENCE=/assets/voice_reference.wav)")
    ref_text = _ref_text()
    model = _load_model()
    wavs, sr = model.generate_voice_clone(
        text=text,
        language=os.environ.get("QWEN_CLONE_LANGUAGE", "English"),
        # NOTE: Urdu is outside the official 10-language list; zero-shot is
        # driven by the raw Urdu text + the reference's Urdu acoustic profile.
        ref_audio=ref,
        ref_text=ref_text,
    )
    sf.write(out_path, wavs[0], sr)
    logger.info("Cloned-voice segment written (%s chars) via %s", len(text), DEFAULT_MODEL)
