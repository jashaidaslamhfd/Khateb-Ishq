#!/usr/bin/env python3
"""Urdu poetry script generator (Groq Llama).

Two sourcing modes, by design (see README → content policy):
- "classic": quote 2 public-domain couplets (Ghalib, Iqbal, Mir — died
  1869/1938/1810 = safely PD) on a theme, plus one short Urdu context line.
  The JSON response includes `source: "classic"` and `poet`.
- "original": generate 2 ORIGINAL AI couplets on the theme — 100%
  copyright-free and uniquely ours. `source: "original"`.

Spoken body is deliberately short (~35-55s): poetry Shorts live and die on
delivery pace, not word count. Validation therefore uses POETRY MODE rules
(3-5 scenes, Urdu text present, no English story-arc constraints).
"""

import json
import logging
import os
import re
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MIN_SCENES = 3
MAX_SCENES = 5
MIN_WORDS = 32          # voiceover counts SCENE CAPTIONS ONLY (hook/cta are metadata)
                        # 2 couplets ≈ 34-48 Urdu words total; the old 45-word floor
                        # rejected valid 2-sher scripts 3/3 times on CI (2026-07-22)
MAX_WORDS = 110
MAX_SCENE_WORDS = 30

# Themes where quoting classics feels natural vs. themes that suit originals
CLASSIC_THEMES = {
    "ghalib": ["dard-e-ishq (sorrow of love)", "mai-khana (the tavern and wine)", "hasti-o-fana (being and nothingness)", "umr guzri (a life spent)"],
    "iqbal": ["khudi (selfhood)", "shaheen (the eagle's ambition)", "umeed-o-junoon (hope and passion)", "watan aur azmat (homeland and greatness)"],
    "mir": ["gham-e-judai (grief of separation)", "yaad (longing and memory)", "be-rukhi (indifference of the beloved)", "sham-e-gham (the evening of sorrow)"],
}
ORIGINAL_THEMES = [
    "tanhai aur raat (loneliness at 2am)", "terhi yaadein (memories that return)", "waqt ke zakhmon ka sulagna",
    "sheher mein tanhai (alone in a crowded city)", "barsaat aur judai (rain and parting)", "ujaale se pehle ka sannata",
    "mohabbat ka akhri paigham (the last message)", "khamoshi ka jawab (an answer made of silence)",
    "safar aur maqsad (the journey and the destination)", "woh jo chale gaye (the ones who left)", "umeed ka diya",
    "sehra ki tarah dil (a heart like a desert)", "guftagu ka wazan adhoori", "chand aur judai",
    "sheesha sa dil (a heart like glass)", "aienay mein waqt", "khushbu ki yaadein", "dua aur sukoon",
    "mazi ki chitthiyan (letters never sent)", "dhund mein sheher", "sooraj dhaltay waqt", "woh ada (that style of theirs)",
    "khwabon ka sheher", "aankhen bolti hain", "raat ka safar", "dil ka dard aur hunar", "aktar judai ke bad",
    "sukoon ki raah mein", "phool aur kaante", "zindagi ek safar", "intezaar ki ghariyan",
]

_PROMPT = """You write for a Pakistani Urdu-poetry Shorts channel. Theme: "{theme}"

Rules — follow exactly:
- ALL spoken text in pure URDU script (اردو رسم الخط), natural poetic register.
- STRICT: absolutely no Roman/Latin letters in title, hook, cta, description or captions — a caption written in Latin letters ("dard", "raat"...) is REJECTED by the validator.
- LENGTH BUDGET: the scenes' captions TOGETHER must total 40-70 Urdu words (≈20-40 seconds at slow poetic pace); each caption 8-{max_scene} words. One full sher (both misre) per poetry scene.
- Return ONLY JSON, exactly in this schema:
{{
  "title": "مختصر اردو عنوان (3 سے 5 الفاظ)",
  "hook": "پہلا جملہ — سننے والے کو روک دے (5 سے 8 الفاظ)",
  "cta": "مختصر فالو کی دعوت اردو میں",
  "description": "ایک جملہ خالص اردو میں — یہ ویڈیو کون سا احساس بیان کرتی ہے",
  "poet": "{poet_note}",
  "scenes": [
    {{"visual": "8-12 English words: moody cinematic image description (rain, old book, dim lamp...) NO text in the image", "caption": "اردو جملہ یا شعر (زیادہ سے زیادہ {max_scene} الفاظ)", "caption_roman": "wahi caption Roman Urdu (Latin letters) mein — Pakistani texting style"}},
    ... {scene_range} scenes total ...
  ]
}}
- caption_roman is REQUIRED per scene: EXACT same sher/meaning as the Urdu caption, written in casual Roman Urdu (Latin script) — this is ONLY for on-screen display; the voice always speaks the Urdu caption.
- Scene 1: the hook line (one striking Urdu line, not a question).
- Middle scenes: the poetry itself — 1 sher per scene, never split a sher across scenes.
- Last scene: a closing line that RETURNS to the opening mood (poetry loops; replay is the algorithm's favorite).
{content_rules}
"""


def _ar_count(text: str) -> int:
    """Word count works for Urdu (space-separated tokens)."""
    return len(text.split())


def _has_urdu(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text or ""))


def _has_latin(text: str) -> bool:
    """Latin letters in a SPOKEN/ON-SCREEN field are fatal: Edge-TTS switches to an
    English voice mid-sher (user report 2026-07-22). Mixed-language captions used
    to slip through because _has_urdu only demanded ONE Arabic-script character."""
    return bool(re.search(r"[A-Za-z]", text or ""))


def _validate_script(script_data: Dict) -> Tuple[bool, List[str]]:
    issues = []
    for field in ("title", "hook", "cta", "scenes"):
        if not script_data.get(field):
            issues.append(f"Missing required field: {field}")
    for field in ("title", "hook", "cta"):
        if _has_latin(script_data.get(field, "")):
            issues.append(f"'{field}' contains Latin letters (English text must never reach screen/voice)")
    scenes = script_data.get("scenes", [])
    if not (MIN_SCENES <= len(scenes) <= MAX_SCENES):
        issues.append(f"Scene count {len(scenes)} (allowed {MIN_SCENES}-{MAX_SCENES})")
    voiceover = " ".join(s.get("caption", "") for s in scenes)
    words = _ar_count(voiceover)
    if not (MIN_WORDS <= words <= MAX_WORDS):
        issues.append(f"Spoken words {words} (allowed {MIN_WORDS}-{MAX_WORDS})")
    for i, scene in enumerate(scenes):
        if not scene.get("visual") or not scene.get("caption"):
            issues.append(f"Scene {i+1} missing visual/caption")
        caption = scene.get("caption", "")
        if caption and not _has_urdu(caption):
            issues.append(f"Scene {i+1} caption is not Urdu script")
        if caption and _has_latin(caption):
            issues.append(f"Scene {i+1} caption contains Latin letters (TTS would speak them in English)")
        if _ar_count(caption) > MAX_SCENE_WORDS:
            issues.append(f"Scene {i+1} caption too long ({_ar_count(caption)} > {MAX_SCENE_WORDS})")
    return not issues, issues


def _extract_json(raw: str) -> Dict:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError(f"No JSON in model reply: {raw[:200]}")
    return json.loads(match.group(0))


def generate_script(theme: str = None, source: str = None) -> Dict:
    """Generate one poetry script. `theme`/`source` default to env/rotation."""
    source = (source or os.environ.get("POETRY_SOURCE", "mix")).lower()
    if source == "mix":
        import random
        poet = random.choice(sorted(CLASSIC_THEMES))
        classic = random.random() < 0.55  # 55% classics keeps proven quality, 45% originals builds identity
        if classic:
            source, poet_key = "classic", poet
        else:
            source, poet_key = "original", None
    else:
        poet_key = source if source in CLASSIC_THEMES else "ghalib"
        source = "classic" if source in CLASSIC_THEMES else "original"

    if not theme:
        if source == "classic":
            import random
            theme = random.choice(CLASSIC_THEMES[poet_key])
        else:
            import random
            theme = random.choice(ORIGINAL_THEMES)

    if source == "classic":
        content_rules = (
            f"- This is a CLASSIC recitation: quote TWO famous couplets by {poet_key.title()} on this theme, quoted EXACTLY "
            "(public domain — he died over 85 years ago), 1 sher per scene.\n"
            "- If you cannot recall an exact sher, write ORIGINAL verses in his style instead and set poet to 'AI (inspired by " + poet_key.title() + ")'."
        )
        poet_note = poet_key.title()
    else:
        content_rules = "- This is ORIGINAL poetry: write TWO original couplets of your own on this theme (never quote living poets — Faraz & Parveen Shakir are still copyrighted!). Set poet to 'Original AI nazm'."
        poet_note = "Original AI nazm"

    prompt = _PROMPT.format(
        theme=theme, poet_note=poet_note, max_scene=MAX_SCENE_WORDS,
        scene_range=f"{MIN_SCENES}-{MAX_SCENES}", content_rules=content_rules)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    from groq import Groq
    client = Groq(api_key=api_key)
    reply = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[{"role": "system", "content": "You are an Urdu poetry director for a sad-poetry Shorts channel. Return only valid JSON."},
                  {"role": "user", "content": prompt}],
        temperature=0.85, max_tokens=1500,
    )
    data = _extract_json(reply.choices[0].message.content)
    data["source"] = source
    data["theme"] = theme
    data.setdefault("poet", poet_note)

    valid, issues = _validate_script(data)
    if not valid:
        logger.warning("Poetry validation failed: %s", issues)
        return None
    data["voiceover"] = " ".join(s["caption"] for s in data["scenes"])
    logger.info("Poetry script ready (%s, poet=%s): %s", source, data["poet"], data["title"])
    return data
