#!/usr/bin/env python3
"""Fail fast if the YouTube OAuth creds do NOT belong to the Khateb-Ishq
channel.  A wrong REFRESH_TOKEN previously uploaded two videos to a stranger
channel while the real Khateb channel stayed empty — this guard makes that
impossible and turns the error into a loud, actionable message instead of
silent junk uploads (and wasted Groq quota).

EXPECTED_CHANNEL_ID can be overridden via workflow `vars`; the default is the
Khateb-Ishq channel (UCUh400Xuscv23BLSegAyU2Q).  Stdlib only.
Exit 0 = verified, exit 1 = wrong/missing/dead token.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

EXPECTED = os.environ.get("EXPECTED_CHANNEL_ID", "UCUh400Xuscv23BLSegAyU2Q")


def main() -> int:
    data = urllib.parse.urlencode({
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("REFRESH_TOKEN", ""),
        "grant_type": "refresh_token",
    }).encode()
    try:
        tok = json.load(urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=data),
            timeout=30))
    except urllib.error.HTTPError as e:
        body = e.read()[:200].decode("utf-8", "replace")
        print(f"::error::REFRESH_TOKEN rejected by Google ({body}). "
              "Re-issue the token from the Khateb-Ishq Google account and update "
              "repo secrets GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / REFRESH_TOKEN.")
        return 1
    access = tok.get("access_token")
    if not access:
        print("::error::No access_token returned — check OAuth client id/secret.")
        return 1

    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true")
    req.add_header("Authorization", f"Bearer {access}")
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        print(f"::error::channels.list failed: {e.read()[:200].decode('utf-8', 'replace')}")
        return 1
    item = (resp.get("items") or [None])[0]
    if not item:
        print("::error::This Google account has NO YouTube channel — secrets point "
              "to the wrong account. Use the Khateb-Ishq Google account.")
        return 1
    cid, title = item["id"], item.get("snippet", {}).get("title", "?")
    if cid != EXPECTED:
        print(f"::error::WRONG CHANNEL — secrets belong to '{title}' ({cid}), "
              f"but the pipeline must upload to Khateb-Ishq ({EXPECTED}). "
              "Fix repo secrets GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / "
              "REFRESH_TOKEN, then re-run. Nothing was uploaded.")
        return 1
    print(f"✓ Channel verified: {title} ({cid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
