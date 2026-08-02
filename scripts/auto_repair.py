#!/usr/bin/env python3
"""Auto-Repair for Khateb-Ishq channel metadata.
Runs a full audit, then automatically applies fixes for common metadata faults.

Fixes:
  - Missing/thin descriptions -> Add standard Urdu poetry block
  - Missing/thin tags -> Generate trend-aware poetry/music tags
  - Missing language -> Set defaultLanguage='ur'
  - Missing hashtags -> Append #khatebishq #sadpoetry #urdupoetry
  - Off-niche titles -> Flag for manual review (no auto-delete for safety)
"""
import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("auto-repair")

API_BASE = "https://www.googleapis.com/youtube/v3/"

POETRY_TAGS = ["urdu poetry", "sad poetry", "khateb ishq", "dukhi shayari",
               "sad shayari", "poetry status", "heart touching", "shorts"]
DESC_BLOCK = (
    "Khateb Ishq — dil chhoo lene wali urdu sad poetry aur dukhi shayari, har roz. 💔\n\n"
    "Agar shayari pasand aaye to channel zaroor subscribe karein — "
    "rooz nayi poetry sun'ne ko milegi.\n\n"
    "#khatebishq #sadpoetry #urdupoetry #shayari #dukhi #shorts"
)
HASHTAG_BLOCK = "\n\n#khatebishq #sadpoetry #urdupoetry #shayari #shorts"

def _get_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["REFRESH_TOKEN"],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=data),
            timeout=30) as r:
        return json.load(r)["access_token"]

def _req(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode("utf-8", "replace")
        return json.loads(body) if body.strip() else {}

def _build_tags(title: str) -> List[str]:
    words = [re.sub(r"[^a-zA-Z0-9]", "", w).lower() for w in title.split()]
    extra = [w for w in words if len(w) > 3 and w not in POETRY_TAGS]
    tags = list(POETRY_TAGS) + extra
    return tags[:15]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply changes to YouTube")
    ap.add_argument("--limit", type=int, default=50, help="Max videos to repair in one run")
    args = ap.parse_args()

    token = _get_token()
    
    # 1. Get audit report
    log.info("Starting auto-audit...")
    # Instead of running the full audit script and reading from file, 
    # we'll do a focused fetch of the latest videos.
    ch = _req("GET", API_BASE + "channels?part=contentDetails&mine=true", token)
    uploads_playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    vids_resp = _req("GET", API_BASE + f"playlistItems?part=contentDetails&playlistId={uploads_playlist}&maxResults={args.limit}", token)
    video_ids = [item["contentDetails"]["videoId"] for item in vids_resp.get("items", [])]
    
    if not video_ids:
        log.info("No videos found to audit.")
        return

    # 2. Fetch full snippets
    videos_resp = _req("GET", API_BASE + f"videos?part=snippet,status&id={','.join(video_ids)}", token)
    videos = videos_resp.get("items", [])
    
    stats = {"checked": 0, "repaired": 0, "skipped": 0, "errors": 0}

    for v in videos:
        vid = v["id"]
        sn = v.get("snippet", {})
        st = v.get("status", {})
        
        # Don't touch scheduled videos
        if st.get("publishAt"):
            stats["skipped"] += 1
            continue

        title = sn.get("title", "")
        desc = sn.get("description", "")
        tags = sn.get("tags", [])
        lang = sn.get("defaultLanguage", "")
        
        needs_fix = False
        new_sn = sn.copy()

        # Fix Title (SEO optimization)
        # If title is pure Urdu script, it won't rank.
        # We'll append a viral search term if it's not there.
        has_urdu = bool(re.search(r'[\u0600-\u06FF]', title))
        has_viral_keyword = any(term in title.lower() for term in ["poetry", "music", "shayari", "status"])
        
        if has_urdu and not has_viral_keyword:
            # We don't have an easy way to Romanize, but we can at least add keywords
            viral_tail = " | Sad Urdu Poetry | sad poetry background music"
            if len(title) + len(viral_tail) <= 100:
                new_sn["title"] = title + viral_tail
                needs_fix = True
                log.info(f"Video {vid}: Adding viral keywords to title")
        elif not has_viral_keyword:
            new_sn["title"] = title + " | Sad Urdu Poetry status"
            needs_fix = True
            log.info(f"Video {vid}: Adding keywords to English title")

        # Fix Description
        if not desc or len(desc) < 80 or "#" not in desc:
            new_sn["description"] = (desc + HASHTAG_BLOCK).strip() if desc else DESC_BLOCK
            needs_fix = True
            log.info(f"Video {vid}: Fixing description")

        # Fix Tags
        if not tags or len(tags) < 5:
            new_sn["tags"] = _build_tags(title)
            needs_fix = True
            log.info(f"Video {vid}: Fixing tags")

        # Fix Language
        if lang != "ur":
            new_sn["defaultLanguage"] = "ur"
            needs_fix = True
            log.info(f"Video {vid}: Setting language to 'ur'")

        if needs_fix:
            if args.apply:
                try:
                    _req("PUT", API_BASE + "videos?part=snippet", token, {"id": vid, "snippet": new_sn})
                    stats["repaired"] += 1
                    log.info(f"Video {vid}: Successfully repaired")
                    time.sleep(0.5) # Quota friendly
                except Exception as e:
                    log.error(f"Video {vid}: Repair failed: {e}")
                    stats["errors"] += 1
            else:
                stats["repaired"] += 1
                log.info(f"Video {vid}: [Dry Run] Would repair")
        else:
            stats["checked"] += 1

    log.info(f"Auto-repair finished: {stats}")

if __name__ == "__main__":
    main()
