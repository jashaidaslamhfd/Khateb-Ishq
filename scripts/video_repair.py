#!/usr/bin/env python3
"""One-shot metadata REPAIR for the Khateb-Ishq channel
(audit 2026-07-25: 83/84 videos faulty).

Three kinds of fixes, one videos.update per video (quota-safe):

A) DELETE 10 videos — off-niche/junk that confuses the poetry niche and the
   monetization review (robot dance, dream home, tea, bridal-bangles promo,
   heaven scenery, 2 dead live-records, 1 garbage, 1 exact-title dup).
   Views sacrificed ≈ 1.2k of the channel's ≈500k lifetime.

B) RETITLE 12 videos — exact-duplicate music titles get distinct honest
   titles (the 'same title 4x' pattern is a repetitious-content risk), and
   hashtag-stuffed/typo'd/cut titles get clean ones. Views kept.

C) METADATA on everything left — defaultLanguage='ur', rebuild missing/
   thin tags (poetry/music base sets + title words), fill empty
   descriptions, append the standard hashtag block where missing.

Run DRY by default; pass --apply to write.
Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / REFRESH_TOKEN env.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("video-repair")

DATA = "https://www.googleapis.com/youtube/v3/"

DELETE_IDS = {
    "YR7kIOh8wuk": "junk ('bast', 3v)",
    "hkP2MDyNmA0": "junk ('live', 13v)",
    "gOSUv5z8Pus": "dead live-record dup (2v)",
    "HnbU8hvcY-k": "dead live-record, off-niche (30v)",
    "4HDdf5enjkA": "off-niche: tea lovers (25v)",
    "U63aYNffT04": "off-niche: robot dance (169v)",
    "aBUqfJ0S81k": "off-niche: dream home (51v)",
    "6Dh9XekfrjM": "off-niche: heaven scenery (244v)",
    "f3Uh55bLVlQ": "off-niche product promo: bridal bangles (541v)",
    "vDOzK4hVBJY": "exact-title duplicate of VXNXwPch7mY (128v vs 542v)",
}

RETITLE = {
    # exact-duplicate music titles -> distinct, honest (keeps views)
    "kGVtOWBjXB8": "Sad Flute Background Music (No Copyright) | Dukhi Shayari Music",
    "srNzuDOqwqc": "Soft Sad Piano Music for Urdu Poetry | Shayari Background (No Copyright)",
    "Qix25IRIFVU": "Emotional Sad Background Music for Poetry Status | No Copyright NCS",
    # hashtag-stuffed / typo'd / cut titles -> clean
    "pyp6ysAohU8": "Sad Background Music No Copyright | Royalty Free NCS Sad Music",
    "Q6MroxkhynU": "Sad Very Sad Lines | Khateb Ishq | Dukhi Status",
    "pqEcrM9QfyU": "Sad Lines - Sad Poetry | Sad Background Music | Khateb Ishq",
    "D1TRgUbye4E": "Latest Sad Poetry Collection | Shayari Status | Khateb Ishq",
    "gwV4A7Q3kcw": "Sad Very Sad Lines | Beautiful Poetry Collection | Khateb Ishq",
    "Yg4jc4Iz4yE": "Urdu Poetry | Love Shayari | Sad Dukhi Shayari | Khateb Ishq",
    "8vk2UTDfKj0": "Sad Background Music for Poetry | Mery Pas Tum Ho Shayari BGM",
    "qiZ572XLygM": "Sad Background Music for Poetry | No Copyright Music for Videos",
    "aqGj-ioTdjs": "Sad Background Music No Copyright | Sad Poetry Music",
}

POETRY_TAGS = ["urdu poetry", "sad poetry", "khateb ishq", "dukhi shayari",
               "sad shayari", "poetry status", "heart touching", "shorts"]
MUSIC_TAGS = ["sad background music", "no copyright music", "shayari background music",
              "sad music", "dukhi music", "poetry music", "ncs", "shorts"]
STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "and", "or", "for",
             "with", "this", "that", "ka", "ki", "ke", "ko", "se", "mein",
             "par", "aur", "ya", "ne", "hi", "bhi", "hai", "ho"}
DESC_BLOCK = (
    "Khateb Ishq — dil chhoo lene wali urdu sad poetry aur dukhi shayari, har roz. 💔\n\n"
    "Agar shayari pasand aaye to channel zaroor subscribe karein — "
    "rooz nayi poetry sun'ne ko milegi.\n\n"
    "#khatebishq #sadpoetry #urdupoetry #shayari #dukhi #shorts"
)
HASHTAG_BLOCK = "\n\n#khatebishq #sadpoetry #urdupoetry #shayari #shorts"


def _token() -> str:
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


def _get_all_video_ids(token, uploads_playlist):
    ids, page_token = [], None
    while True:
        params = {"part": "contentDetails", "playlistId": uploads_playlist,
                  "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        page = _req("GET", DATA + "playlistItems?" + urllib.parse.urlencode(params), token)
        for item in page.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page_token = page.get("nextPageToken")
        if not page_token:
            return ids


def _build_tags(title, is_music):
    base = MUSIC_TAGS if is_music else POETRY_TAGS
    words = [w.strip("#,.|!?'\"").lower() for w in title.split()]
    extra = [w for w in words if len(w) > 3 and w not in STOPWORDS and w not in base]
    tags = list(base) + extra
    seen, out = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:15]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    token = _token()
    stats = {"deleted": 0, "updated": 0, "skipped": 0, "errors": 0}

    # 0) resolve uploads playlist once
    ch = _req("GET", DATA + "channels?part=contentDetails&mine=true", token)
    items = ch.get("items") or []
    if not items:
        log.error("no channel visible with this token — aborting")
        return 1
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # A) deletes
    for vid, why in DELETE_IDS.items():
        if not args.apply:
            log.info("[dry] would DELETE %s (%s)", vid, why)
        else:
            try:
                _req("DELETE", DATA + f"videos?id={vid}", token)
                stats["deleted"] += 1
                log.info("DELETED %s (%s)", vid, why)
            except Exception as exc:
                stats["errors"] += 1
                log.warning("delete %s failed: %s", vid, exc)
        time.sleep(0.5)

    # B+C) per-video metadata fix
    all_ids = [v for v in _get_all_video_ids(token, uploads) if v not in DELETE_IDS]
    for idx in range(0, len(all_ids), 50):
        batch = all_ids[idx:idx + 50]
        resp = _req("GET", DATA + "videos?" + urllib.parse.urlencode({
            "part": "snippet,status", "id": ",".join(batch), "maxResults": "50"}), token)
        for video in resp.get("items", []):
            vid = video["id"]
            sn = video.get("snippet", {})
            st = video.get("status", {})
            if st.get("publishAt"):  # never touch the scheduled poetry upload
                stats["skipped"] += 1
                continue
            title = (sn.get("title") or "").strip()
            desc = (sn.get("description") or "").strip()
            tags = sn.get("tags") or []
            is_music = "music" in title.lower() or "ncs" in title.lower()

            new_title = RETITLE.get(vid, title)
            new_desc = desc
            if not desc:
                new_desc = DESC_BLOCK
            elif len(desc) < 80 or "#" not in desc:
                new_desc = desc + HASHTAG_BLOCK
            new_tags = tags
            if len(tags) < 5:
                new_tags = _build_tags(new_title, is_music)
            new_lang = "ur"

            changed = (new_title != title or new_desc != desc
                       or new_tags != tags or sn.get("defaultLanguage") != new_lang)
            if not changed:
                stats["skipped"] += 1
                continue
            if not args.apply:
                stats["updated"] += 1
                log.info("[dry] UPDATE %s  title:%s lang:%s->ur tags:%d->%d desc:%d->%dc",
                         vid, "Y" if new_title != title else "-",
                         sn.get("defaultLanguage"), len(tags), len(new_tags),
                         len(desc), len(new_desc))
                continue
            payload = {"id": vid, "snippet": {
                "title": new_title,
                "description": new_desc[:5000],
                "categoryId": sn.get("categoryId", "22"),
                "tags": new_tags,
                "defaultLanguage": new_lang,
                **({"defaultAudioLanguage": sn["defaultAudioLanguage"]}
                   if sn.get("defaultAudioLanguage") else {}),
            }}
            try:
                _req("PUT", DATA + "videos?part=snippet", token, payload)
                stats["updated"] += 1
                log.info("UPDATED %s (%s)", vid, new_title[:50])
            except Exception as exc:
                stats["errors"] += 1
                log.warning("update %s failed: %s", vid, exc)
            time.sleep(0.4)

    log.info("done (apply=%s) %s", args.apply, stats)
    print(json.dumps({"date": dt.date.today().isoformat(),
                      "apply": args.apply, **stats}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
