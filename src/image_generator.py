#!/usr/bin/env python3
"""Scene image generation — thin wrapper over the proven multi-provider
fallback registry (src/image_providers.py) with within-video dedupe.

REGISTRY CONTRACT (must stay in sync with src/image_providers.py):
    provider = {"name": str, "env_keys": [...], "generate": fn}
    data, ext = provider["generate"](prompt, seed, scene_text)
  - seed       : fresh random int per call (variety between scenes/videos)
  - scene_text : the scene's Urdu caption (some providers append style words)
  - returns    : (image_bytes, "jpg"/"png")
"""

import hashlib
import logging
import os
import random

from image_providers import available_providers

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MIN_BYTES = 4000  # smaller payloads are error pages / empty responses, not images
STYLE = "cinematic moody sad poetry aesthetic, soft rain, dim warm lamp, film grain, 9:16 vertical, no text, no watermark, no people faces"


def _provider_generate(provider: dict, prompt: str, seed: int, scene_text):
    """Call one registry provider with its (prompt, seed, scene_text) contract.
    Returns (image_bytes, ext). Raises on provider-side failure."""
    result = provider["generate"](prompt, seed, scene_text)
    if isinstance(result, tuple):
        data, ext = result
    else:  # a provider that returns bare bytes
        data, ext = result, "jpg"
    return data, ext


def generate_scene_image(index: int, scene: dict, used_hashes: set, used_fallbacks: set) -> dict:
    # `used_fallbacks` kept in the signature for main.py compatibility —
    # per-video dedupe now happens on raw image BYTES (stronger than URLs).
    visual = (scene.get("visual") or "rainy window at night")[:220]
    prompt = f"{visual}, {STYLE}"
    scene_text = scene.get("caption") or None
    os.makedirs("output/images", exist_ok=True)

    for provider in available_providers():
        try:
            seed = random.randint(1000, 999999)  # fresh seed per provider try
            data, ext = _provider_generate(provider, prompt, seed, scene_text)
            if not data or len(data) < MIN_BYTES:
                logger.warning("Provider %s returned too-small response for scene %d", provider["name"], index + 1)
                continue
            digest = hashlib.sha256(bytes(data)).hexdigest()
            if digest in used_hashes:
                logger.info("Provider %s returned a repeated image — skipping", provider["name"])
                continue
            path = f"output/images/scene_{index}.{ext}"
            with open(path, "wb") as fh:
                fh.write(data)
            used_hashes.add(digest)
            logger.info("Scene %d image via %s (%d KB)", index + 1, provider["name"], len(data) // 1024)
            return {"path": path, "source": provider["name"], "media_type": "image", "bytes": len(data)}
        except Exception as exc:
            logger.warning("Provider %s failed for scene %d: %s", provider["name"], index + 1, exc)

    # Final safety net: local placeholder (dark texture)
    placeholder = "assets/placeholder.png"
    if os.path.exists(placeholder):
        import shutil
        path = f"output/images/scene_{index}.jpg"
        shutil.copy(placeholder, path)
        logger.warning("All providers failed for scene %d — using placeholder texture", index + 1)
        return {"path": path, "source": "placeholder", "media_type": "image"}
    raise RuntimeError(f"No image for scene {index + 1} and no placeholder available")
