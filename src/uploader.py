#!/usr/bin/env python3
"""YouTube uploader for Khateb-Ishq — OAuth user creds, publishAt scheduling.

Videos upload PRIVATE with status.publishAt = next Pakistan peak (env-driven:
PUBLISH_TIMEZONE / PUBLISH_SLOTS), and YouTube itself flips them public at
that exact time. Synthetic-media disclosure always on. Same pattern as the
proven SKILLOR uploader, minus Facebook (this channel is YouTube-only).
"""

import hashlib
import json
import logging
import os
import time

import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from scheduler import compute_publish_at

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MADE_FOR_KIDS = os.environ.get("YT_MADE_FOR_KIDS", "false").lower() == "true"
YT_PRIVACY_STATUS = os.environ.get("YT_PRIVACY_STATUS", "private").strip().lower()
YT_SCHEDULE_PUBLISH = os.environ.get("YT_SCHEDULE_PUBLISH", "true").lower() == "true"
if YT_PRIVACY_STATUS not in {"private", "unlisted", "public"}:
    raise ValueError("YT_PRIVACY_STATUS must be private, unlisted, or public")
DEFAULT_LANG = os.environ.get("CHANNEL_LANGUAGE", "ur").strip() or "ur"
CATEGORY_ID = os.environ.get("YT_CATEGORY_ID", "24")  # 24 = Entertainment
UPLOAD_STATE_PATH = os.environ.get("UPLOAD_STATE_PATH", "data/upload_state.json")


def _load_state() -> dict:
    try:
        with open(UPLOAD_STATE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(UPLOAD_STATE_PATH) or ".", exist_ok=True)
    tmp = UPLOAD_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, UPLOAD_STATE_PATH)


def _fingerprint(script_data: dict) -> str:
    material = "|".join(str(script_data.get(k, "")).strip().lower()
                       for k in ("theme", "title", "voiceover"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _yt_client():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ.get("REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    return build("youtube", "v3", credentials=creds)


def _build_description(script_data: dict, tags: list) -> str:
    poet = script_data.get("poet", "")
    title = script_data.get("title", "")
    lines = [
        f"🎙 {title} — اردو شاعری" if title else "🎙 اردو شاعری",
        f"شاعر: {poet} | نظم خوانی: AI Urdu narration" if poet else "نظم خوانی: AI Urdu narration",
        script_data.get("description", ""),   # Urdu sentence (see script_generator prompt)
        "",
        "Sad Urdu poetry status 💔 dukhi shayari — heart touching 2 line poetry with AI Urdu narration.",
        "",
        "روزانہ نئی شاعری — فالو/سبسکرائب کیجیے تاکہ کوئی نظم رہ نہ جائے۔",
        "",
        "#urdupoetry #shayari #sadpoetry " + " ".join(f"#{t.replace(' ', '')}" for t in tags[:5]),
    ]
    return "\n".join(line for line in lines if line is not None)[:4000]


# Search-cluster title tails — the channel's 746k views mostly come from the
# "sad background music / dukhi status" SEARCH cluster (views audit 2026-07),
# so every new original recitation rides the same demand with a bilingual
# title: Urdu hook + rotating Roman keyword tail (+ poet credit).
_SEARCH_TAILS = (
    "sad urdu poetry",
    "dukhi status",
    "heart touching shayari",
    "2 line sad poetry",
    "urdu poetry status",
)


def _seo_title(script_data: dict) -> str:
    """Build the final upload title.  Rotation is deterministic (md5 of
    title+poet) so retries of the SAME script never churn the title, and a
    batch of uploads spreads across all five search tails."""
    import hashlib
    base = (script_data.get("title") or "اردو شاعری").strip()
    poet = (script_data.get("poet") or "").strip()
    idx = int(hashlib.md5(f"{base}|{poet}".encode("utf-8")).hexdigest()[:6], 16) % len(_SEARCH_TAILS)
    poet_tag = f" | {poet.split(' (')[0]}" if poet and poet.lower() != "original" else ""
    tail = _SEARCH_TAILS[idx] + poet_tag
    title = f"{base} | {tail}"
    if len(title) > 97:  # shave the Urdu base, never the search tail
        keep = max(20, 97 - len(tail) - 4)
        title = f"{base[:keep].rstrip()}… | {tail}"
    return title[:100]


def upload_all(video_path: str, thumb_path: str, script_data: dict) -> dict:
    fingerprint = _fingerprint(script_data)
    state = _load_state()
    existing = state.get(fingerprint)
    if existing and existing.get("status") == "completed":
        logger.info("Duplicate content — skipping re-upload (%s)", existing.get("youtube_video_id"))
        return {"youtube_success": True, "youtube_video_id": existing.get("youtube_video_id"), "duplicate": True}

    base_tags = script_data.get("tags") or ["urdu poetry", "shayari", "sad poetry", "urdu shorts", script_data.get("poet", "khateb e ishq")]
    # Always append the winning search-cluster tags (deduped, short: the
    # 500-char tag limit is nowhere near).
    cluster = ["sad urdu poetry", "dukhi status", "heart touching poetry",
               "urdu poetry status", "2 line poetry"]
    tags = list(base_tags) + [t for t in cluster if t not in base_tags]
    status_body = {
        "privacyStatus": YT_PRIVACY_STATUS,
        "selfDeclaredMadeForKids": MADE_FOR_KIDS,
        "containsSyntheticMedia": True,
    }
    if YT_SCHEDULE_PUBLISH:
        publish_at = compute_publish_at()
        status_body["privacyStatus"] = "private"
        status_body["publishAt"] = publish_at
        logger.info("Scheduled → YouTube auto-publishes at %s (next PK peak)", publish_at)

    body = {"snippet": {
            "title": _seo_title(script_data),
            "description": _build_description(script_data, tags),
            "categoryId": CATEGORY_ID,
            "tags": tags,
            "defaultLanguage": DEFAULT_LANG,
            "defaultAudioLanguage": DEFAULT_LANG,
        }, "status": status_body}

    state[fingerprint] = {"status": "started", "title": body["snippet"]["title"], "started_at": time.time()}
    _save_state(state)

    yt = _yt_client()
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = yt.videos().insert(
                part="snippet,status", body=body,
                media_body=MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True))
            response = request.execute()
            video_id = response.get("id")
            if not video_id:
                raise RuntimeError(f"Upload returned no id: {response}")
            state[fingerprint] = {"status": "completed", "title": body["snippet"]["title"],
                                  "youtube_video_id": video_id, "completed_at": time.time()}
            _save_state(state)
            logger.info("Uploaded: https://youtu.be/%s", video_id)
            if thumb_path and os.path.exists(thumb_path):
                try:
                    yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
                except Exception as exc:
                    logger.warning("Thumbnail failed (video is live anyway): %s", exc)
            return {"youtube_success": True, "youtube_video_id": video_id,
                    "publish_at": status_body.get("publishAt")}
        except HttpError as exc:
            last_error = exc
            logger.warning("YouTube attempt %d failed: %s", attempt, exc)
            time.sleep(10 * attempt)
    state[fingerprint]["status"] = "failed"
    _save_state(state)
    raise RuntimeError(f"YouTube upload failed after {MAX_RETRIES} attempts: {last_error}")
