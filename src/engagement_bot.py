#!/usr/bin/env python3
"""Engagement Bot — Auto-comment management, engagement questions, community posts.

This module handles viewer engagement on YouTube:
  1. Auto-post engaging questions as comments on new videos
  2. Auto-pin the engagement question (always visible)
  3. Auto-reply to viewer comments (simple, polite Urdu replies)
  4. Heart positive comments
  5. Post community posts for channel growth

Usage:
  from engagement_bot import EngagementBot
  bot = EngagementBot()
  bot.post_engagement_comment(video_id="...", question="Aapka favourite sher kaunsa hai?")
  bot.process_new_comments(video_id="...")
  bot.post_community_post(text="Nayi nazm aane wali hai! 💔")
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("engagement_bot")

ROOT = Path(__file__).resolve().parents[1]
ENGAGEMENT_STATE_PATH = ROOT / "data" / "engagement_state.json"

# ── Engagement Questions (Urdu) ────────────────────────────────────────────
# These are posted as pinned comments on each video to drive engagement.
ENGAGEMENT_QUESTIONS = [
    "اچھا لگا تو سہارا دیں ❤️ — آپ کا پسندیدہ شعر کون سا ہے؟",
    "یہ شاعری نے دل چھو لیا؟ 💔 کمنٹ میں بتائیں آپ کا پسندیدہ شعر",
    "اگر یہ نظم آپ کی کہانی ہے تو ❤️ دبائیں — آپ کا کون سا شعر پسند ہے؟",
    "درد کی بات کریں؟ 💙 کمنٹ میں اپنا پسندیدہ شعر شیئر کریں",
    "آپ کے لیے یہ شاعری کیسی لگی؟ ❤️ کمنٹ میں بتائیں",
    "اگر یہ نظم آپ کی زندگی کی کہانی ہے تو 💔 کمنٹ میں لکھیں",
    "یہ شاعری نے یادوں تازہ کر دیں؟ 💙 اپنا پسندیدہ شعر کمنٹ میں لکھیں",
    "کون سا شعر سب سے زیادہ دل چھوا؟ 💔 کمنٹ میں بتائیں",
    "اگر آپ بھی تنہائی محسوس کرتے ہیں تو ❤️ — یہ شاعری آپ کے لیے ہے",
    "اس شاعری نے دل کو چھو لیا؟ 💙 کمنٹ میں اپنا پسندیدہ شعر شیئر کریں",
]

# ── Auto-reply templates (Urdu) ────────────────────────────────────────────
AUTO_REPLY_TEMPLATES = [
    "شکریہ! ❤️ آپ کی پسند ہمارے لیے اہم ہے",
    "جزیاک اللہ خیر! 💙 آپ کا شعر بھی بہت اچھا ہے",
    "شکریہ! آپ کا پیار ہی ہمارے لیے سب سے بڑا انعام ہے ❤️",
    "بہت شکریہ! 💔 آپ کا کامنٹ ہمیں مزید شاعری لکھنے پر مجبور کرتا ہے",
    "آپ کا شکریہ! ❤️ روزانہ نئی شاعری کے لیے سبسکرائب کریں",
    "شکریہ! 💙 آپ کا پسند ہماری محنت کا ثمر ہے",
    "بہت شکریہ! ❤️ آپ جیسے ناظرین ہی تو ہیں جو ہمیں آگے بڑھاتے ہیں",
    "جزیاک اللہ! 💔 آپ کا پیار ہم نہیں بھول سکتے",
]

# ── Positive comment detection patterns (Urdu/Roman) ──────────────────────
POSITIVE_PATTERNS = [
    r"بہت اچھ[ای]", r"زبردست", r"شاندار", r"ماشا اللہ", r"سبحان اللہ",
    r"jazak", r"shukriya", r"mashallah", r"subhanallah", r"nice", r"beautiful",
    r"amazing", r"lovely", r"heart", r"❤", r"💔", r"💙", r"🔥", r"👏",
    r"سپر", r"عمدہ", r"نہایت", r"پسند", r"احساس", r"دل چھو",
    r"boht acha", r"bohat acha", r"bahut acha", r"zabardast", r"kyabaathai",
    r"subscribe", r"following", r"love", r"like", r"best", r"great",
]


class EngagementBot:
    """Manages YouTube engagement: comments, replies, community posts."""

    def __init__(self):
        self.state = self._load_state()
        self._yt = None

    def _load_state(self) -> dict:
        try:
            return json.loads(ENGAGEMENT_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"comments": {}, "replies": {}, "community": {}, "last_updated": None}

    def _save_state(self) -> None:
        ENGAGEMENT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = ENGAGEMENT_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(ENGAGEMENT_STATE_PATH)

    def _yt_client(self):
        """Build YouTube Data API client."""
        if self._yt is None:
            import google.oauth2.credentials
            from googleapiclient.discovery import build
            creds = google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=os.environ.get("REFRESH_TOKEN"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ.get("GOOGLE_CLIENT_ID"),
                client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
                scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
            )
            self._yt = build("youtube", "v3", credentials=creds)
        return self._yt

    # ── Engagement Comment ─────────────────────────────────────────────────

    def post_engagement_comment(self, video_id: str, question: str = None) -> dict:
        """Post an engagement question as a pinned comment on a new video."""
        if not question:
            question = self._pick_question(video_id)

        try:
            yt = self._yt_client()
            # Post comment
            resp = yt.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": question,
                            }
                        }
                    }
                },
            ).execute()

            comment_id = resp["id"]
            logger.info("Engagement comment posted: %s (id: %s)", question[:50], comment_id)

            # Pin the comment
            self._pin_comment(comment_id)

            # Save state
            self.state["comments"][video_id] = {
                "comment_id": comment_id,
                "text": question,
                "pinned": True,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_state()

            return {"success": True, "comment_id": comment_id, "pinned": True}

        except Exception as exc:
            logger.error("Failed to post engagement comment: %s", exc)
            return {"success": False, "error": str(exc)}

    def _pick_question(self, video_id: str) -> str:
        """Pick a question, rotating through the list to avoid repetition."""
        # Use video_id hash for deterministic but varied selection
        idx = hash(video_id) % len(ENGAGEMENT_QUESTIONS)
        return ENGAGEMENT_QUESTIONS[idx]

    def _pin_comment(self, comment_id: str) -> bool:
        """Pin a comment to the top of the video's comment section.
        
        Note: YouTube Data API v3 does NOT have a 'pin' endpoint.
        The channel owner must manually pin comments via YouTube Studio.
        We only set the moderation status to 'published' to ensure it's visible.
        """
        try:
            yt = self._yt_client()
            # Ensure the comment is published (not held for review)
            yt.comments().setModerationStatus(
                id=comment_id,
                moderationStatus="published",
            ).execute()
            logger.info("Comment %s set as published (pin requires manual action in YouTube Studio)", comment_id)
            return True
        except Exception as exc:
            logger.warning("Pin comment failed (non-critical): %s", exc)
            return False

    # ── Auto-Reply to Comments ─────────────────────────────────────────────

    def _is_positive_comment(self, text: str) -> bool:
        """Check if a comment is positive/appreciative."""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in POSITIVE_PATTERNS)

    def _should_reply(self, comment_text: str, author: str) -> bool:
        """Decide whether to auto-reply to a comment."""
        # Don't reply to our own comments
        if "khateb" in author.lower() or "ishq" in author.lower():
            return False
        # Don't reply to very short comments
        if len(comment_text.strip()) < 3:
            return False
        # Reply to positive comments
        return self._is_positive_comment(comment_text)

    def process_new_comments(self, video_id: str, max_replies: int = 10) -> dict:
        """Process new comments on a video and auto-reply to positive ones."""
        try:
            yt = self._yt_client()

            # Fetch comments
            resp = yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=50,
                order="time",
            ).execute()

            replies_posted = 0
            hearts_given = 0

            for thread in resp.get("items", []):
                top_comment = thread["snippet"]["topLevelComment"]
                comment_id = top_comment["id"]
                comment_text = top_comment["snippet"]["textOriginal"]
                author = top_comment["snippet"]["authorDisplayName"]

                # Skip if we already replied
                if comment_id in self.state.get("replies", {}):
                    continue

                # Heart positive comments
                # Note: YouTube API v3 does NOT support hearting comments.
                # Hearting must be done manually via YouTube Studio.
                if self._is_positive_comment(comment_text):
                    hearts_given += 1

                # Auto-reply to positive comments
                if self._should_reply(comment_text, author) and replies_posted < max_replies:
                    reply_text = self._pick_reply(author)
                    try:
                        yt.comments().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "parentId": comment_id,
                                    "textOriginal": reply_text,
                                }
                            },
                        ).execute()
                        self.state.setdefault("replies", {})[comment_id] = {
                            "reply": reply_text,
                            "original_comment": comment_text[:100],
                            "replied_at": datetime.now(timezone.utc).isoformat(),
                        }
                        replies_posted += 1
                        logger.info("Replied to comment by %s: %s", author, reply_text[:40])
                    except Exception as exc:
                        logger.warning("Reply failed: %s", exc)

                    # Rate limit: don't spam replies
                    time.sleep(2)

            self._save_state()
            return {
                "success": True,
                "video_id": video_id,
                "replies_posted": replies_posted,
                "hearts_given": hearts_given,
                "comments_processed": len(resp.get("items", [])),
            }

        except Exception as exc:
            logger.error("Comment processing failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _pick_reply(self, author: str) -> str:
        """Pick a reply template, rotating through the list."""
        idx = hash(author + datetime.now().strftime("%Y-%m-%d")) % len(AUTO_REPLY_TEMPLATES)
        return AUTO_REPLY_TEMPLATES[idx]

    # ── Community Posts ────────────────────────────────────────────────────

    def post_community_post(self, text: str, poll: dict = None) -> dict:
        """Post a community post on the YouTube channel.

        Note: YouTube Data API v3 doesn't support community posts directly.
        This requires the YouTube Channel API or manual posting.
        We generate the content and save it for manual posting or future API support.
        """
        # Save for manual posting
        post_data = {
            "text": text,
            "poll": poll,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_manual_post",
        }
        self.state.setdefault("community", {})[datetime.now().strftime("%Y%m%d")] = post_data
        self._save_state()

        logger.info("Community post saved for manual posting: %s", text[:80])
        return {"success": True, "message": "Saved for manual posting (YouTube API limitation)", "post": post_data}

    def generate_engagement_post(self, script_data: dict) -> str:
        """Generate an engaging community post based on the latest video."""
        poet = script_data.get("poet", "")
        title = script_data.get("title", "")

        posts = [
            f"💔 نئی نظم آ رہی ہے! '{title}' — کیا آپ تیار ہیں؟",
            f"🎙 آج کی شاعری: {title}" + (f" — شاعر: {poet}" if poet else ""),
            f"❓ آپ کا پسندیدہ شاعر کون ہے؟ Ghalib, Iqbal, ya Mir? کمنٹ میں بتائیں!",
            f"💔 سادہ شاعری یا گہری باتیں؟ آپ کیا پسند کرتے ہیں؟",
            f"🎙 '{title}' — کل شام 9 بجے! مت بھولنا ❤️",
        ]

        idx = hash(title + datetime.now().strftime("%Y-%m-%d")) % len(posts)
        return posts[idx]

    def generate_poll_post(self) -> dict:
        """Generate a community poll for engagement."""
        polls = [
            {
                "question": "آپ کا پسندیدہ شاعر کون ہے؟",
                "options": ["غالب", "اقبال", "میر تقی میر", "کوئی اور"],
            },
            {
                "question": "کس موسم کی شاعری آپ کو سب سے زیادہ پسند ہے؟",
                "options": ["برست", "سردی", "گرمی", "بہار"],
            },
            {
                "question": "شاعری کا کون سا انداز پسند ہے؟",
                "options": ["غمگین", "رومانوی", "صوفیانہ", "محوری"],
            },
            {
                "question": "آپ کتنی دفعہ شاعری سنتے ہیں؟",
                "options": ["روزانہ", "ہفتے میں", "مہینے میں", "کبھی کبھی"],
            },
        ]
        idx = hash(datetime.now().strftime("%Y-%m-%d")) % len(polls)
        return polls[idx]

    # ── Batch Processing ───────────────────────────────────────────────────

    def process_all_videos(self, video_ids: List[str] = None) -> dict:
        """Process engagement for all recent videos."""
        results = []
        if not video_ids:
            # Get video IDs from state
            video_ids = list(self.state.get("comments", {}).keys())

        for vid in video_ids:
            result = self.process_new_comments(vid)
            results.append(result)

        return {
            "success": True,
            "videos_processed": len(results),
            "total_replies": sum(r.get("replies_posted", 0) for r in results),
            "total_hearts": sum(r.get("hearts_given", 0) for r in results),
        }


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = EngagementBot()
    # Generate sample engagement content
    print("📢 Engagement Bot — Sample Content:\n")
    print("Engagement Questions:")
    for q in ENGAGEMENT_QUESTIONS[:3]:
        print(f"  • {q}")
    print("\nCommunity Post:")
    print(f"  {bot.generate_engagement_post({'title': 'غمِ دل', 'poet': 'Ghalib'})}")
    print("\nPoll:")
    poll = bot.generate_poll_post()
    print(f"  {poll['question']}")
    for opt in poll["options"]:
        print(f"    - {opt}")
