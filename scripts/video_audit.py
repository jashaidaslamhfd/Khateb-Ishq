#!/usr/bin/env python3
"""Read-only METADATA audit of EVERY video on the Khateb-Ishq channel
(Urdu sad-poetry channel — expected standard: URDU).

Scans the whole uploads list and flags per-video faults:

  TITLE
    title_empty / title_truncated / duplicate_title
    title_english_only   (pure Latin title with NO Urdu-script chars and no
                          roman poetry words — e.g. "Dream Home" era)
  DESCRIPTION
    description_empty / description_thin (<80) / description_no_hashtag
  TAGS
    tags_missing / tags_thin (<5)
  LANGUAGE
    language_not_ur      (defaultLanguage missing or != ur)
  NICHE (sad poetry / shayari)
    off_niche            (no Urdu-script char AND no poetry marker word in
                          title OR description — robot-dance/dream-home junk)
  THUMBNAIL (hint only)
    thumbnail_possibly_auto
  FORMAT / STATE (informational)
    not_short (>65s), not_public, scheduled_pending

Writes data/video_audit_<date>.json and prints a human summary.
Stdlib only. READ-ONLY. Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET /
REFRESH_TOKEN env.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DATA = "https://www.googleapis.com/youtube/v3/"

URDU_SCRIPT_RE = re.compile(r"[ ؀-ۿݐ-ݿ࣠-ࣿ]")
POETRY_MARKERS = (
    "poetry", "shayari", "shayri", "shairy", "sad", "ghazal", "urdu",
    "dard", "ishq", "mohabbat", "muhabbat", "dukhi", "dil", "sukoon",
    "bewafa", "judai", "tanhai", "udaas", "rooh", "sukun", "husn",
    "khateb", "broken", "heart touching", "zindagi", "jaun", "galib",
    "ghalib", "iqbal", "mir", "faiz", "bulleh", "waris", "kalaam",
    "status", "lines", "poem", "nazm", "adeeb", "sufi", "punjabi",
    "zaat", "aansu", "gum", "sham", "raat", "poetrystatus",
)
EN_DANGLERS = ("the", "a", "an", "of", "to", "in", "on", "at", "by", "for",
               "and", "or", "but", "when", "why", "how", "your", "our",
               "my", "his", "her", "its", "their", "this", "that",
               "with", "from", "is", "are", "was", "were", "ka", "ki",
               "ke", "ko", "se", "mein", "par", "aur", "ya", "ne", "hi",
               "bhi", "to", "tak", "wala", "wali", "wale")
WORD_RE = re.compile(r"[a-zA-Z']+")


def _access_token() -> str:
    payload = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GET {url[:90]}... -> {exc.code}: {body}") from exc


def _query(path: str, params: dict, token: str) -> dict:
    return _get(DATA + path + "?" + urllib.parse.urlencode(params), token)


def _has_urdu_script(text: str) -> bool:
    return bool(URDU_SCRIPT_RE.search(text or ""))


def _has_poetry_marker(text: str) -> bool:
    low = " " + (text or "").lower() + " "
    return any(" " + m in low or low.strip().startswith(m) for m in POETRY_MARKERS) or \
        any(m in low for m in ("shayari", "poetry", "ishq", "ghazal", "mohabbat"))


def _audit_video(video: dict) -> list:
    faults = []
    sn = video.get("snippet", {})
    st = video.get("status", {})
    cd = video.get("contentDetails", {})

    title = (sn.get("title") or "").strip()
    desc = (sn.get("description") or "").strip()
    tags = sn.get("tags") or []

    if not title:
        faults.append("title_empty")
    else:
        last = WORD_RE.findall(title)
        last = last[-1].lower() if last else ""
        if (last in EN_DANGLERS or title.endswith(("…", " -", " |", ":"))
                or (len(title) >= 95 and not title.endswith(("?", "!", ".")))):
            faults.append("title_truncated")
        if not _has_urdu_script(title) and not _has_poetry_marker(title):
            faults.append("title_english_only")

    if not desc:
        faults.append("description_empty")
    else:
        if len(desc) < 80:
            faults.append("description_thin")
        if "#" not in desc:
            faults.append("description_no_hashtag")

    if not tags:
        faults.append("tags_missing")
    elif len(tags) < 5:
        faults.append("tags_thin")

    if sn.get("defaultLanguage") != "ur":
        faults.append("language_not_ur")

    blob = title + " " + desc[:200]
    if not _has_urdu_script(blob) and not _has_poetry_marker(blob):
        faults.append("off_niche")

    if "maxres" not in (sn.get("thumbnails") or {}):
        faults.append("thumbnail_possibly_auto")

    duration = cd.get("duration", "")
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", duration)
    seconds = 0.0
    if match:
        seconds = (int(match.group(1) or 0) * 3600
                   + int(match.group(2) or 0) * 60
                   + float(match.group(3) or 0))
    if seconds > 65:
        faults.append("not_short")
    if st.get("privacyStatus") != "public" and not st.get("publishAt"):
        faults.append("not_public")
    if st.get("publishAt"):
        faults.append("scheduled_pending")
    return faults


def main() -> int:
    token = _access_token()
    channels = _query("channels", {"part": "contentDetails,statistics", "mine": "true"}, token)
    items = channels.get("items") or []
    if not items:
        print("AUDIT FAILED: no channel visible with this token")
        return 1
    uploads_playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    total_uploads = int(items[0].get("statistics", {}).get("videoCount", 0))

    video_ids = []
    page_token = None
    while True:
        params = {"part": "contentDetails", "playlistId": uploads_playlist,
                  "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        page = _query("playlistItems", params, token)
        for item in page.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = page.get("nextPageToken")
        if not page_token:
            break

    videos = []
    for idx in range(0, len(video_ids), 50):
        batch = video_ids[idx:idx + 50]
        resp = _query("videos", {
            "part": "snippet,status,contentDetails,statistics",
            "id": ",".join(batch),
            "maxResults": "50",
        }, token)
        videos.extend(resp.get("items", []))

    report = []
    title_registry = {}
    for v in videos:
        sn = v.get("snippet", {})
        faults = _audit_video(v)
        norm = re.sub(r"\W+", "", (sn.get("title") or "").lower())
        entry = {
            "video_id": v["id"],
            "url": f"https://youtu.be/{v['id']}",
            "title": sn.get("title", ""),
            "published_at": sn.get("publishedAt"),
            "views": v.get("statistics", {}).get("viewCount"),
            "language": sn.get("defaultLanguage"),
            "tags_count": len(sn.get("tags") or []),
            "desc_len": len(sn.get("description") or ""),
            "faults": faults,
        }
        report.append(entry)
        title_registry.setdefault(norm, []).append(v["id"])
    dup_owner = set()
    for ids in title_registry.values():
        if len(ids) > 1:
            dup_owner.update(ids)
    for entry in report:
        if entry["video_id"] in dup_owner:
            entry["faults"].append("duplicate_title")

    from collections import Counter
    counter = Counter(f for e in report for f in e["faults"])
    clean = [e for e in report if not e["faults"]]
    faulty = [e for e in report if e["faults"]]

    out = {
        "date": dt.date.today().isoformat(),
        "channel": "Khateb-Ishq (UCUh400Xuscv23BLSegAyU2Q)",
        "channel_video_count": total_uploads,
        "videos_scanned": len(report),
        "videos_clean": len(clean),
        "videos_faulty": len(faulty),
        "fault_counts": dict(counter.most_common()),
        "faulty_videos": sorted(faulty, key=lambda e: -len(e["faults"])),
    }
    os.makedirs("data", exist_ok=True)
    path = f"data/video_audit_{dt.date.today().isoformat()}.json"
    with open(path, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print("=" * 64)
    print(f"VIDEO METADATA AUDIT — KHATEB-ISHQ — {out['date']}")
    print(f"channel videos: {total_uploads} | scanned: {len(report)}")
    print(f"clean: {len(clean)} | faulty: {len(faulty)}")
    print("-" * 64)
    for fault, count in counter.most_common():
        print(f"  {fault:26s} {count}")
    print("-" * 64)
    for e in out["faulty_videos"]:
        print(f"  {e['video_id']}  views={e['views']}  {sorted(set(e['faults']))}")
        print(f"      {e['title'][:75]}")
    print(f"\nsaved -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
