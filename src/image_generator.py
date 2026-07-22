#!/usr/bin/env python3
"""Scene image generation — thin wrapper over the proven 9-provider
fallback registry (src/image_providers.py) with within-video dedupe."""

import hashlib
import logging
import os

import requests

from image_providers import available_providers

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 90
STYLE = "cinematic moody sad poetry aesthetic, soft rain, dim warm lamp, film grain, 9:16 vertical, no text, no watermark, no people faces"


def _download(url: str, path: str) -> bool:
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 8000:
            with open(path, "wb") as fh:
                fh.write(resp.content)
            return True
    except Exception as exc:
        logger.warning("Image download failed: %s", exc)
    return False


def generate_scene_image(index: int, scene: dict, used_hashes: set, used_fallbacks: set) -> dict:
    visual = (scene.get("visual") or "rainy window at night")[:220]
    prompt = f"{visual}, {STYLE}"
    os.makedirs("output/images", exist_ok=True)

    providers = available_providers()
    for provider in providers:
        try:
            result = provider["generate"](prompt)
            url = result if isinstance(result, str) else (result or {}).get("url") or (result or {}).get("image_url")
            if not url:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()
            if digest in used_hashes or url in used_fallbacks:
                logger.info("Provider %s returned a repeated image — skipping", provider["name"])
                continue
            path = f"output/images/scene_{index}.jpg"
            if _download(url, path):
                used_hashes.add(digest)
                logger.info("Scene %d image via %s", index + 1, provider["name"])
                return {"path": path, "source": provider["name"], "media_type": "image", "url": url}
        except Exception as exc:
            logger.warning("Provider %s failed for scene %d: %s", provider["name"], index + 1, exc)

    # Final safety net: local placeholder (dark texture) — never repeated URLs
    placeholder = "assets/placeholder.png"
    if os.path.exists(placeholder):
        import shutil
        path = f"output/images/scene_{index}.jpg"
        shutil.copy(placeholder, path)
        logger.warning("All providers failed for scene %d — using placeholder texture", index + 1)
        return {"path": path, "source": "placeholder", "media_type": "image"}
    raise RuntimeError(f"No image for scene {index + 1} and no placeholder available")
