#!/usr/bin/env python3
"""Multi-Platform Poster — Auto-post to TikTok, Instagram Reels, Facebook Reels.

This module extends Khateb-Ishq's reach beyond YouTube by automatically
reposting Shorts to other vertical-video platforms. Each platform has its
own API and content requirements, but the video format (9:16, <60s) is
already compatible.

Platform support:
  1. TikTok — Direct Posting API (via TikTok for Developers)
  2. Instagram Reels — Content Publishing API (via Facebook Graph API)
  3. Facebook Reels — Graph API Reels endpoint

Usage:
  from multi_platform import MultiPlatformPoster
  poster = MultiPlatformPoster()
  results = poster.post_all(video_path="output/final.mp4", script_data={...})
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("multi_platform")

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_STATE_PATH = ROOT / "data" / "platform_state.json"

# ── Platform Configuration ─────────────────────────────────────────────────

PLATFORM_CONFIG = {
    "tiktok": {
        "enabled_env": "TIKTOK_ENABLED",
        "default_enabled": "false",
        "required_env": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_OPEN_ID"],
        "max_title_length": 150,
        "max_description_length": 150,
        "supported_formats": ["mp4"],
        "max_duration_seconds": 60,
    },
    "instagram": {
        "enabled_env": "INSTAGRAM_ENABLED",
        "default_enabled": "false",
        "required_env": ["IG_ACCESS_TOKEN", "IG_BUSINESS_ACCOUNT_ID"],
        "max_title_length": 2200,
        "max_description_length": 2200,
        "supported_formats": ["mp4"],
        "max_duration_seconds": 90,
    },
    "facebook": {
        "enabled_env": "FACEBOOK_ENABLED",
        "default_enabled": "false",
        "required_env": ["FB_ACCESS_TOKEN", "FB_PAGE_ID"],
        "max_title_length": 5000,
        "max_description_length": 5000,
        "supported_formats": ["mp4"],
        "max_duration_seconds": 60,
    },
}


class MultiPlatformPoster:
    """Posts videos to multiple platforms with platform-specific optimizations."""

    def __init__(self):
        self.state = self._load_state()
        self.enabled_platforms = self._detect_platforms()

    def _load_state(self) -> dict:
        try:
            return json.loads(PLATFORM_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"platforms": {}, "last_updated": None}

    def _save_state(self) -> None:
        PLATFORM_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = PLATFORM_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PLATFORM_STATE_PATH)

    def _detect_platforms(self) -> List[str]:
        """Detect which platforms are configured and enabled."""
        enabled = []
        for platform, config in PLATFORM_CONFIG.items():
            is_enabled = os.environ.get(config["enabled_env"], config["default_enabled"]).lower() in ("true", "1", "yes")
            if is_enabled:
                # Check if all required env vars are set
                missing = [k for k in config["required_env"] if not os.environ.get(k)]
                if missing:
                    logger.warning("%s enabled but missing env vars: %s", platform.title(), missing)
                else:
                    enabled.append(platform)
                    logger.info("✅ %s ready for posting", platform.title())
        return enabled

    # ── Platform-specific description builders ─────────────────────────────

    def _build_tiktok_description(self, script_data: dict) -> str:
        """Build TikTok-optimized description with trending hashtags."""
        poet = script_data.get("poet", "")
        title = script_data.get("title", "اردو شاعری")
        tags = script_data.get("tags", [])

        # TikTok prefers short, punchy descriptions with trending hashtags
        desc = f"🎙 {title}"
        if poet and poet.lower() != "original":
            desc += f" — {poet}"
        desc += "\n\n"

        # TikTok-specific hashtags
        tiktok_tags = ["urdupoetry", "shayari", "sadpoetry", "fyp", "viral", "pakistan", "desi"]
        all_tags = tiktok_tags + [t for t in tags[:5] if t.lower() not in tiktok_tags]
        desc += " ".join(f"#{t.replace(' ', '')}" for t in all_tags[:8])

        return desc[:PLATFORM_CONFIG["tiktok"]["max_description_length"]]

    def _build_instagram_description(self, script_data: dict) -> str:
        """Build Instagram Reels-optimized description."""
        poet = script_data.get("poet", "")
        title = script_data.get("title", "اردو شاعری")
        tags = script_data.get("tags", [])

        desc = f"🎙 {title}\n\n"
        if poet and poet.lower() != "original":
            desc += f"شاعر: {poet}\n"
        desc += "Sad Urdu poetry status 💔 dukhi shayari\n\n"
        desc += "روزانہ نئی شاعری — فالو کیجیے!\n\n"

        # Instagram prefers 20-30 hashtags
        ig_tags = [
            "urdupoetry", "shayari", "sadpoetry", "urdushayari", "poetry",
            "sadstatus", "hearttouching", "2linepoetry", "viralpoetry",
            "desipoetry", "pakistanipoetry", "dukhishayari", "dard",
            "gham", "ishq", "mohabbat", "lovepoetry", "reels",
        ]
        all_tags = ig_tags + [t for t in tags[:10] if t.lower() not in ig_tags]
        desc += " ".join(f"#{t.replace(' ', '')}" for t in all_tags[:25])

        return desc[:PLATFORM_CONFIG["instagram"]["max_description_length"]]

    def _build_facebook_description(self, script_data: dict) -> str:
        """Build Facebook Reels-optimized description."""
        poet = script_data.get("poet", "")
        title = script_data.get("title", "اردو شاعری")

        desc = f"🎙 {title} — اردو شاعری\n\n"
        if poet and poet.lower() != "original":
            desc += f"شاعر: {poet}\n"
        desc += (
            "Sad Urdu poetry status 💔 dukhi shayari — heart touching 2 line poetry "
            "with AI Urdu narration.\n\n"
            "روزانہ نئی شاعری — فالو/سبسکرائب کیجیے تاکہ کوئی نظم رہ نہ جائے۔\n\n"
            "#urdupoetry #shayari #sadpoetry #dukhistatus #hearttouching"
        )
        return desc[:PLATFORM_CONFIG["facebook"]["max_description_length"]]

    # ── Platform Posting Methods ───────────────────────────────────────────

    def _post_tiktok(self, video_path: str, script_data: dict) -> dict:
        """Post to TikTok via Direct Posting API."""
        access_token = os.environ["TIKTOK_ACCESS_TOKEN"]
        open_id = os.environ["TIKTOK_OPEN_ID"]

        description = self._build_tiktok_description(script_data)

        # Step 1: Initialize upload
        try:
            init_resp = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "post_info": {
                        "title": description[:PLATFORM_CONFIG["tiktok"]["max_title_length"]],
                        "privacy_level": os.environ.get("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": "",  # We'll use direct upload
                    },
                },
                timeout=30,
            )
            if init_resp.status_code != 200:
                return {"success": False, "platform": "tiktok", "error": f"Init failed: {init_resp.status_code}"}

            # Step 2: Upload video (chunked upload)
            publish_id = init_resp.json().get("data", {}).get("publish_id")
            upload_url = init_resp.json().get("data", {}).get("upload_url")

            if upload_url and publish_id:
                with open(video_path, "rb") as f:
                    video_data = f.read()

                upload_resp = requests.put(
                    upload_url,
                    data=video_data,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(video_data)),
                    },
                    timeout=300,
                )
                if upload_resp.status_code not in (200, 201):
                    return {"success": False, "platform": "tiktok", "error": f"Upload failed: {upload_resp.status_code}"}

            return {
                "success": True,
                "platform": "tiktok",
                "publish_id": publish_id,
                "description": description[:100],
            }

        except Exception as exc:
            logger.error("TikTok posting failed: %s", exc)
            return {"success": False, "platform": "tiktok", "error": str(exc)}

    def _post_instagram(self, video_path: str, script_data: dict) -> dict:
        """Post to Instagram Reels via Content Publishing API."""
        access_token = os.environ["IG_ACCESS_TOKEN"]
        account_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]

        description = self._build_instagram_description(script_data)

        try:
            # Step 1: Create container
            container_resp = requests.post(
                f"https://graph.facebook.com/v19.0/{account_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": "",  # Direct upload would need a public URL
                    "caption": description,
                    "access_token": access_token,
                },
                timeout=30,
            )
            if container_resp.status_code != 200:
                return {"success": False, "platform": "instagram",
                        "error": f"Container creation failed: {container_resp.status_code} {container_resp.text[:200]}"}

            container_id = container_resp.json().get("id")

            # Step 2: Wait for processing, then publish
            for _ in range(30):  # Max 5 minutes wait
                time.sleep(10)
                status_resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{container_id}",
                    params={"fields": "status_code", "access_token": access_token},
                    timeout=30,
                )
                status = status_resp.json().get("status_code")
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    return {"success": False, "platform": "instagram", "error": "Processing failed"}

            # Step 3: Publish
            publish_resp = requests.post(
                f"https://graph.facebook.com/v19.0/{account_id}/media_publish",
                data={"creation_id": container_id, "access_token": access_token},
                timeout=30,
            )
            if publish_resp.status_code != 200:
                return {"success": False, "platform": "instagram",
                        "error": f"Publish failed: {publish_resp.status_code}"}

            media_id = publish_resp.json().get("id")
            return {
                "success": True,
                "platform": "instagram",
                "media_id": media_id,
                "description": description[:100],
            }

        except Exception as exc:
            logger.error("Instagram posting failed: %s", exc)
            return {"success": False, "platform": "instagram", "error": str(exc)}

    def _post_facebook(self, video_path: str, script_data: dict) -> dict:
        """Post to Facebook Reels via Graph API."""
        access_token = os.environ["FB_ACCESS_TOKEN"]
        page_id = os.environ["FB_PAGE_ID"]

        description = self._build_facebook_description(script_data)

        try:
            # Upload video as a reel
            with open(video_path, "rb") as f:
                upload_resp = requests.post(
                    f"https://graph.facebook.com/v19.0/{page_id}/video_reels",
                    data={
                        "access_token": access_token,
                        "description": description,
                    },
                    files={"video_file": ("video.mp4", f, "video/mp4")},
                    timeout=300,
                )

            if upload_resp.status_code != 200:
                return {"success": False, "platform": "facebook",
                        "error": f"Upload failed: {upload_resp.status_code} {upload_resp.text[:200]}"}

            reel_id = upload_resp.json().get("id")
            return {
                "success": True,
                "platform": "facebook",
                "reel_id": reel_id,
                "description": description[:100],
            }

        except Exception as exc:
            logger.error("Facebook posting failed: %s", exc)
            return {"success": False, "platform": "facebook", "error": str(exc)}

    # ── Main Posting Method ────────────────────────────────────────────────

    def post_all(self, video_path: str, script_data: dict) -> dict:
        """Post to all enabled platforms. Returns summary of results."""
        results = {}
        total_success = 0
        total_attempts = 0

        if not self.enabled_platforms:
            logger.info("No platforms configured for cross-posting (only YouTube)")
            return {"success": True, "platforms": {}, "message": "YouTube-only mode"}

        for platform in self.enabled_platforms:
            total_attempts += 1
            logger.info("📱 Posting to %s...", platform.title())

            if platform == "tiktok":
                result = self._post_tiktok(video_path, script_data)
            elif platform == "instagram":
                result = self._post_instagram(video_path, script_data)
            elif platform == "facebook":
                result = self._post_facebook(video_path, script_data)
            else:
                result = {"success": False, "platform": platform, "error": "Unknown platform"}

            results[platform] = result
            if result.get("success"):
                total_success += 1
                logger.info("✅ %s posted successfully", platform.title())
            else:
                logger.warning("❌ %s failed: %s", platform.title(), result.get("error"))

            # Save state
            self.state["platforms"][platform] = {
                "last_post": datetime.now(timezone.utc).isoformat(),
                "success": result.get("success", False),
                "video_id": result.get("media_id") or result.get("reel_id") or result.get("publish_id"),
            }

        self._save_state()

        return {
            "success": total_success > 0,
            "platforms": results,
            "total_attempts": total_attempts,
            "total_success": total_success,
            "message": f"Posted to {total_success}/{total_attempts} platforms",
        }

    def get_status(self) -> dict:
        """Get current multi-platform status."""
        return {
            "enabled_platforms": self.enabled_platforms,
            "last_posts": self.state.get("platforms", {}),
            "available_platforms": list(PLATFORM_CONFIG.keys()),
        }


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    poster = MultiPlatformPoster()
    status = poster.get_status()
    print("Multi-Platform Poster Status:")
    print(f"  Enabled: {status['enabled_platforms']}")
    print(f"  Available: {status['available_platforms']}")
    print(f"  Last posts: {json.dumps(status['last_posts'], indent=2)}")
