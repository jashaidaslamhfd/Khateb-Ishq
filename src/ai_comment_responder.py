#!/usr/bin/env python3
"""AI Comment Responder — LLM-powered contextual Urdu replies to YouTube comments.

2026 MUST-HAVE: YouTube's algorithm HEAVILY favors videos with active comment
sections. Auto-replies with generic templates ("شکریہ!") now get flagged as
spam by YouTube's 2026 bot detection. You need CONTEXTUAL, LLM-generated
replies that reference the actual comment content.

This module replaces the old template-based replies with:
  1. LLM-generated contextual Urdu replies (via Groq/Gemini)
  2. Reply references the actual comment content
  3. Variable reply length (short, medium, long)
  4. Emotion-aware replies (sad, appreciative, questioning)
  5. Anti-spam safety: rate limiting, never reply to own comments

Usage:
  from ai_comment_responder import AICommentResponder
  responder = AICommentResponder()
  reply = responder.generate_reply("Bohat khoobsurat shayari hai, dil ko chhoo gayi")
  print(reply)  # "Wah jee, aapki tareef ne dil khush kar diya! 🙏 Ye sher..."
"""

import json
import logging
import os
import re
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai_comment_responder")

ROOT = Path(__file__).resolve().parents[1]

# ── Reply personality (channel voice) ──────────────────────────────────────
CHANNEL_PERSONALITY = """Tum Khateb-e-Ishq channel ke owner ho — ek Urdu poetry channel.
Tumhara andaaz:
  - Garam, mehmano ki tarah baat karo (jaise ghar mein mehman aaye ho)
  - Urdu aur Roman Urdu dono use karo (jaise aam Pakistani/Indian baat karte hain)
  - Emoji use karo par zyada nahi (❤️ 💔 🙏 suffice)
  - Hamesha shukriya ada karo + viewer ki baat acknowledge karo
  - Kabhi bhi generic "شکریہ" mat likho — SPECIFIC reply do
  - 1-2 lines mein reply do (Shorts comment section mein lamba reply boring lagta hai)
  - Agar viewer ne koi sher likha hai, uski tareef karo
  - Agar viewer ne dukh share kiya hai, empathy dikhao
  - Kabhi bhi "subscribe" ya "like" mat bol in reply — ye spam lagta hai
"""

# ── Anti-spam safety ───────────────────────────────────────────────────────
MAX_REPLIES_PER_HOUR = 5
MAX_REPLIES_PER_VIDEO = 10
MIN_COMMENT_LENGTH = 3
OWN_CHANNEL_KEYWORDS = ["khateb", "ishq", "khateb-e-ishq", "khatebeishq"]


class AICommentResponder:
    """Generate contextual Urdu replies to YouTube comments using LLM."""

    def __init__(self):
        self.reply_history = self._load_history()
        self._groq_client = None

    def _load_history(self) -> dict:
        hist_path = ROOT / "data" / "ai_reply_history.json"
        try:
            return json.loads(hist_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"replies": {}, "last_updated": None}

    def _save_history(self) -> None:
        hist_path = ROOT / "data" / "ai_reply_history.json"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        self.reply_history["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = hist_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.reply_history, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(hist_path)

    def _get_groq_client(self):
        """Lazy-init Groq client."""
        if self._groq_client is None:
            from groq import Groq
            self._groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        return self._groq_client

    def _is_own_comment(self, author: str) -> bool:
        """Check if comment is from our own channel."""
        author_lower = author.lower()
        return any(kw in author_lower for kw in OWN_CHANNEL_KEYWORDS)

    def _is_spam_comment(self, text: str) -> bool:
        """Detect spam comments (link drops, irrelevant content)."""
        spam_patterns = [
            r"http[s]?://",  # Links
            r"subscribe\s+to\s+my",  # Sub4sub
            r"check\s+out\s+my\s+channel",  # Self-promo
            r"(\d{1,3}\s*){3,}",  # Phone numbers
            r"free\s+money",  # Scam
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in spam_patterns)

    def _detect_emotion(self, text: str) -> str:
        """Detect the emotion of a comment for context-aware replies."""
        text_lower = text.lower()

        # Sad/pain expressions
        sad_words = ["dard", "dukhi", "rona", "aansu", "tanhai", "judai", "bewafai",
                     "zakhm", "gham", "dil", "todo", "tut", "ro", "rona"]
        if any(w in text_lower for w in sad_words):
            return "sad"

        # Appreciation
        appreciate_words = ["bohat", "boht", "zabardast", "khoobsurat", "amazing",
                           "beautiful", "lovely", "mashallah", "best", "nice",
                           "acha", "achha", "pyara", "shukriya"]
        if any(w in text_lower for w in appreciate_words):
            return "appreciative"

        # Question
        if any(w in text_lower for w in ["kya", "kon", "kab", "kaise", "kyun", "kaun"]):
            return "questioning"

        # Sharing a sher/couplet
        if any(w in text_lower for w in ["shayari", "sher", "ghazal", "poetry", "kalam"]):
            return "sharing_poetry"

        return "neutral"

    def generate_reply(self, comment_text: str, author: str = "",
                       video_title: str = "", emotion: str = None) -> str:
        """Generate a contextual Urdu reply to a YouTube comment.

        Uses LLM (Groq/Gemini) for contextual replies. Falls back to
        smart templates if LLM is unavailable.
        """
        if not comment_text or len(comment_text.strip()) < MIN_COMMENT_LENGTH:
            return None

        if self._is_own_comment(author):
            return None

        if self._is_spam_comment(comment_text):
            return None

        detected_emotion = emotion or self._detect_emotion(comment_text)

        # Try LLM-generated reply
        try:
            reply = self._generate_llm_reply(comment_text, author, video_title, detected_emotion)
            if reply:
                return reply
        except Exception as exc:
            logger.warning("LLM reply failed, falling back to smart template: %s", exc)

        # Fallback: smart template reply
        return self._generate_template_reply(comment_text, author, detected_emotion)

    def _generate_llm_reply(self, comment_text: str, author: str,
                            video_title: str, emotion: str) -> Optional[str]:
        """Generate reply using Groq LLM."""
        client = self._get_groq_client()

        prompt = f"""{CHANNEL_PERSONALITY}

Viewer ka comment: "{comment_text}"
Viewer ka naam: {author or "Unknown"}
Video title: {video_title or "Sad Urdu Poetry"}
Comment ki emotion: {emotion}

Is comment ka 1-2 line reply likho Roman Urdu mein. SPECIFIC ho — viewer ki baat acknowledge karo.
Sirf reply likho, koi extra explanation nahi."""

        try:
            resp = client.chat.completions.create(
                model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Reply to: {comment_text}"}
                ],
                max_tokens=100,
                temperature=0.8,
            )
            reply = resp.choices[0].message.content.strip()
            # Clean up reply (remove quotes, etc.)
            reply = reply.strip('"').strip("'").strip()
            if len(reply) > 200:
                reply = reply[:197] + "..."
            return reply
        except Exception as exc:
            logger.warning("Groq reply generation failed: %s", exc)
            return None

    def _generate_template_reply(self, comment_text: str, author: str,
                                 emotion: str) -> str:
        """Smart template-based reply (fallback when LLM is unavailable)."""
        templates = {
            "sad": [
                "Dard aapka samajh sakta hoon 💔 — ye shayari aapke liye hai",
                "Allah aapko sabr de 🙏 — ye poetry aapke dil ki baat keh rahi hai",
                "Aapka dard in alfaaz mein bayaan ho gaya 💙",
                "Hum sab kuch samajh sakte hain ❤️ — ye shayari aapke gham ka saathi hai",
            ],
            "appreciative": [
                "Shukriya aapki tareef ka! ❤️ Ye encouragement hi hai humara",
                "Aapka pyaar hi humari energy hai 🙏",
                "Bohot shukriya! 💙 Aap jaise viewers ke liye hi poetry likhti hai",
                "JazakAllah! ❤️ Aapki tareef ne dil khush kar diya",
            ],
            "questioning": [
                "Achha sawaal hai! 🤔 Aage aur poetry aane wali hai — subscribe rakhein",
                "Hum is baare mein aage aur content laayenge 🙏",
                "Shukriya sawaal ka! ❤️ Aap jaise sawal humein aur aage badhate hain",
            ],
            "sharing_poetry": [
                "Wah! Aapka sher bhi bohot khoobsurat hai ❤️",
                "Aapki shayari mein bhi gehraai hai! 🙏 Kamaal hai",
                "Zabardast! 💙 Aap bhi shayar hain kya?",
                "Aapka kalam bhi dil ko chhoota hai ❤️ — humein aur sunao!",
            ],
            "neutral": [
                "Shukriya aapke comment ka! ❤️",
                "Aapka feedback humare liye bohot valuable hai 🙏",
                "Bohot shukriya! 💙 Aap jaise viewers hi humari energy hain",
            ],
        }

        emotion_templates = templates.get(emotion, templates["neutral"])
        return random.choice(emotion_templates)

    def process_video_comments(self, video_id: str, max_replies: int = 5) -> dict:
        """Process comments on a video and generate contextual replies."""
        try:
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
            yt = build("youtube", "v3", credentials=creds)
        except Exception as exc:
            logger.error("YouTube API client failed: %s", exc)
            return {"success": False, "error": str(exc)}

        # Fetch comments
        try:
            resp = yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=50,
                order="time",
            ).execute()
        except Exception as exc:
            logger.error("Failed to fetch comments: %s", exc)
            return {"success": False, "error": str(exc)}

        replies_posted = 0
        skipped = 0

        for thread in resp.get("items", []):
            if replies_posted >= max_replies:
                break

            top_comment = thread["snippet"]["topLevelComment"]
            comment_id = top_comment["id"]
            comment_text = top_comment["snippet"]["textOriginal"]
            author = top_comment["snippet"]["authorDisplayName"]

            # Skip if already replied
            if comment_id in self.reply_history.get("replies", {}):
                skipped += 1
                continue

            # Generate reply
            reply_text = self.generate_reply(comment_text, author)
            if not reply_text:
                skipped += 1
                continue

            # Post reply
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

                self.reply_history.setdefault("replies", {})[comment_id] = {
                    "reply": reply_text,
                    "original_comment": comment_text[:100],
                    "author": author,
                    "replied_at": datetime.now(timezone.utc).isoformat(),
                }
                replies_posted += 1
                logger.info("Replied to %s: %s", author, reply_text[:40])

                # Rate limit: don't spam
                time.sleep(3)

            except Exception as exc:
                logger.warning("Failed to post reply: %s", exc)

        self._save_history()

        return {
            "success": True,
            "video_id": video_id,
            "replies_posted": replies_posted,
            "skipped": skipped,
        }


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    responder = AICommentResponder()
    # Test with sample comments
    test_comments = [
        ("Bohat khoobsurat shayari hai, dil ko chhoo gayi", "Ahmed"),
        ("Aaj raat tanhai mein ye shayari sun raha hoon, dukh ho raha hai", "Sara"),
        ("Ghalib sahab ka kalam hai kya ye?", "Ali"),
        ("Mera dil toot gaya hai, ye shayari meri kahani hai", "Fatima"),
    ]

    for comment, author in test_comments:
        reply = responder.generate_reply(comment, author)
        print(f"\n💬 {author}: {comment}")
        print(f"   🤖 Reply: {reply}")
