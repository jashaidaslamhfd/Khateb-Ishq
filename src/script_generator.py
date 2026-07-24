#!/usr/bin/env python3
"""Urdu poetry script generation — Groq (Llama 3.3 70B), khateb-ishq quality bar.

Contract (see tests/test_poetry_core.py, tests/test_runtime_compat.py):

    generate_script(theme: str) -> dict:
        title, hook, cta, description, poet, source ("classic"/"original"),
        tags, theme, topic, voiceover, scenes: [
            {"visual": <English scene description for the image model>,
             "caption": <Urdu-script sher/couplet — this gets SPOKEN>,
             "caption_roman": <optional Roman-Urdu, on-screen only, never spoken>},
            ...
        ]

    _validate_script(data: dict) -> (bool, list[str] issues)

HARD RULE — why this file exists / why it matters for accent quality:
Edge-TTS's ur-PK voices are genuinely native Urdu/Pakistani neural voices —
they nail the Urdu/Hindi-region lahja. But if a SPOKEN field (title, hook,
cta, or a scene's `caption`) contains even one stray Latin/Roman word, the
TTS engine switches to an English phoneme set for that word mid-sentence —
that's what produces the jarring "English accent" glitch in an otherwise
Urdu narration. So every spoken field must be 100% Urdu script. Roman text
is only ever allowed in `caption_roman`, which is on-screen-only and is
never passed to the TTS engine (see video_editor._pick_display_caption).
"""

import json
import logging
import os
import random
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MIN_SCENES = 3
MAX_SCENES = 5
MIN_SPOKEN_WORDS = int(os.environ.get("MIN_SPOKEN_WORDS", "32"))  # 2 couplets ≈ 34-48 Urdu words — a hard 40-word floor
                               # rejects valid 2-sher scripts 3/3 times (CI lesson 2026-07-22)
MAX_SPOKEN_WORDS = int(os.environ.get("MAX_SPOKEN_WORDS", "110"))
MAX_GEN_ATTEMPTS = 3

# Arabic script block + presentation forms — covers Urdu (Nastaliq/Naskh).
_URDU_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Content policy (README): classics are safe public-domain poets; these two
# are still under copyright and must never be used on a monetized channel.
_CLASSIC_POETS = {
    "ghalib": "Mirza Ghalib (d.1869)",
    "iqbal": "Allama Iqbal (d.1938)",
    "mir": "Mir Taqi Mir (d.1810)",
    # Punjabi Sufi masters — public domain, and the channel's 40k-view
    # "Kamli waly Muhammad" upload proved this Sufi cluster pulls views.
    "bullehshah": "Bulleh Shah (d.1757)",
    "warisshah": "Waris Shah (d.1798)",
}
_FORBIDDEN_POETS = ("ahmad faraz", "parveen shakir")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _has_urdu(text: str) -> bool:
    return bool(_URDU_RE.search(text or ""))


def _has_latin(text: str) -> bool:
    return bool(_LATIN_RE.search(text or ""))


def _check_urdu_field(label: str, text: str, issues: list) -> None:
    """A spoken field must be non-empty, Urdu-script, and free of Latin words."""
    text = (text or "").strip()
    if not text:
        issues.append(f"{label} is empty")
        return
    if not _has_urdu(text):
        issues.append(f"{label} is not Urdu script: {text[:60]!r}")
        return
    if _has_latin(text):
        issues.append(f"{label} contains Latin characters: {text[:60]!r}")


def _validate_script(data: dict):
    """Returns (is_valid, issues). `description` is metadata-only (YouTube
    description), never spoken/rendered as captions, so it is NOT required
    to be pure Urdu — it may legitimately be bilingual or English."""
    issues = []
    if not isinstance(data, dict):
        return False, ["Script is not a JSON object"]

    _check_urdu_field("title", data.get("title", ""), issues)
    _check_urdu_field("hook", data.get("hook", ""), issues)
    _check_urdu_field("cta", data.get("cta", ""), issues)

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < MIN_SCENES:
        got = len(scenes) if isinstance(scenes, list) else 0
        issues.append(f"Need at least {MIN_SCENES} scenes, got {got}")
        scenes = scenes if isinstance(scenes, list) else []

    spoken_words = 0
    for i, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            issues.append(f"Scene {i} is not an object")
            continue
        caption = scene.get("caption", "")
        _check_urdu_field(f"Scene {i} caption", caption, issues)
        spoken_words += len((caption or "").split())
        if not (scene.get("visual") or "").strip():
            issues.append(f"Scene {i} is missing a visual description")
        # caption_roman is allowed to be Roman/Latin — on-screen only, never
        # spoken — so it is intentionally NOT run through _check_urdu_field.

    if spoken_words < MIN_SPOKEN_WORDS:
        issues.append(f"Spoken words too few ({spoken_words} < {MIN_SPOKEN_WORDS})")
    elif spoken_words > MAX_SPOKEN_WORDS:
        issues.append(f"Spoken words too many ({spoken_words} > {MAX_SPOKEN_WORDS})")

    return (len(issues) == 0), issues


# --------------------------------------------------------------------------- #
# Poet / mode selection (content policy: 55% classics / 45% originals)
# --------------------------------------------------------------------------- #
def _pick_mode(pinned: str = None):
    forced = (pinned or os.environ.get("POETRY_SOURCE", "mix")).strip().lower()
    if forced in _CLASSIC_POETS:
        return "classic", forced
    if forced == "original":
        return "original", None
    # mix
    if random.random() < 0.55:
        poet = random.choice(list(_CLASSIC_POETS))
        return "classic", poet
    return "original", None


# --------------------------------------------------------------------------- #
# Groq call
# --------------------------------------------------------------------------- #
def _client():
    from groq import Groq
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _build_prompt(theme: str, mode: str, poet_key: str, feedback: list = None) -> list:
    if mode == "classic":
        poet_name = _CLASSIC_POETS[poet_key]
        source_rule = (
            f"Poet: quote/recite AUTHENTIC, well-attested couplets by {poet_name} only. "
            f"Never invent lines and attribute them to a real poet. "
            f"Never use Ahmad Faraz or Parveen Shakir (still copyrighted) — if unsure, "
            f"pick a different well-attested couplet by {poet_name} instead."
        )
        if poet_key in ("bullehshah", "warisshah"):
            source_rule += (
                " This poet wrote in Punjabi: use their SHORT, simple Sufiyana lines "
                "written in Urdu script (Shahmukhi), with easy pronunciation for Urdu "
                "TTS — no long or obscure vocabulary."
            )
    else:
        poet_name = "AI Original"
        source_rule = (
            "Write 100% original Urdu couplets in the classical ghazal/nazm tradition "
            "(you own the copyright — never copy or paraphrase a real poet's line)."
        )

    system = (
        "Tum ek professional Urdu shair aur short-video script writer ho, jo Pakistani "
        "audience ke liye viral 'sad poetry' YouTube Shorts likhte ho. Sirf khaalis, "
        "adabi Urdu rasm-ul-khat mein likho — kabhi bhi Roman Urdu ya English lafz "
        "'caption' ya 'title'/'hook'/'cta' fields mein na ghusne do (aik bhi English "
        "lafz TTS ka lahja kharab kar deta hai). Poetry ka معیار (quality) buland ho: "
        "asal, gehri, khoobsurat tashbeehat (imagery), sahi bahr/wazn ka ehsaas, aur "
        "waqai dard/ehsaas jo dil ko chhoo jaye — sasta ya generic na ho.\n"
        "EMOTION TARGET (RULA DENE WALA): har caption kisi COMMON, REAL dard ko chhooe — "
        "bewafai, judai, tanhai, intezaar, raat ki yaadein, apno ka be-his pana — jo har "
        "aam aadmi apne dil se milaye. Abstract falsafa YA mushaira-style pech-o-kham "
        "NAHI; seedha awaam ka dard, simple alfaaz, gehra ehsaas.\n"
        "VIRAL HOOK: scene 1 pehle 2 second mein dil chubha de — ek relatable pain "
        "statement (maslan 'jab apna bana hua bhi paraya lage...'). SAWAL na poochho — "
        "zakhm dikhao. Hook ko question form mein kabhi mat likho.\n"
        "CLIMAX = AANSO: aakhri scene sab se tez dard ho taake sunne wala video dobara "
        "chalaye (rewatch = reach); koi halki/masali closing nahi.\n\n"
        "Output STRICTLY valid JSON, no markdown fences, no preamble, no explanation — "
        "just the JSON object, matching this exact shape:\n"
        "{\n"
        '  "title": "<Urdu title, short, punchy>",\n'
        '  "hook": "<one Urdu line, first 2-3 seconds, must grab attention>",\n'
        '  "cta": "<one Urdu call-to-action line, e.g. follow/subscribe ka Urdu jumla>",\n'
        '  "description": "<one Urdu OR English sentence for the YouTube description>",\n'
        '  "poet": "<poet name if classic, else \\"Original\\">",\n'
        '  "scenes": [\n'
        '    {"visual": "<ENGLISH visual description for an AI image model — moody, '
        'cinematic, no on-image text/people/logos>",\n'
        '     "caption": "<Urdu sher/line to be SPOKEN — pure Urdu script only>",\n'
        '     "caption_roman": "<REQUIRED: exact same line in casual Roman Urdu — '
        'Pakistani texting style — used for on-screen captions; voice always speaks '
        'the Urdu caption, never this one>"}\n'
        "    ... (3 to 5 scenes total)\n"
        "  ]\n"
        "}\n\n"
        f"{source_rule}\n"
        f"Total spoken words across all scene captions combined should land roughly "
        f"between {MIN_SPOKEN_WORDS} and {MAX_SPOKEN_WORDS} words (a 30-57 second Short)."
    )

    user = f"Theme/topic: {theme}\n\nGenerate the JSON script now."
    if feedback:
        user += (
            "\n\nYour previous attempt had these problems — fix ALL of them and "
            "resend the full corrected JSON:\n- " + "\n- ".join(feedback)
        )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(raw[start:end + 1])


def _default_tags(poet: str, mode: str) -> list:
    tags = ["urdu poetry", "shayari", "sad poetry", "urdu shorts"]
    if mode == "classic" and poet:
        tags.append(poet)
    else:
        tags.append("original shayari")
    return tags


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def generate_script(theme: str) -> dict:
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    mode, poet_key = _pick_mode()
    client = _client()

    feedback = None
    last_data = None
    for attempt in range(1, MAX_GEN_ATTEMPTS + 1):
        messages = _build_prompt(theme, mode, poet_key, feedback)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.9,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            data = _extract_json(raw)
        except Exception as exc:
            logger.warning("Groq generation attempt %d failed: %s", attempt, exc)
            feedback = [f"Previous attempt errored: {exc}. Resend strict valid JSON only."]
            continue

        last_data = data
        valid, issues = _validate_script(data)
        if valid:
            poet_name = data.get("poet") or (_CLASSIC_POETS.get(poet_key, "Original") if mode == "classic" else "Original")
            lowered = poet_name.lower()
            if any(bad in lowered for bad in _FORBIDDEN_POETS):
                logger.warning("Forbidden poet %s slipped through — retrying with original mode", poet_name)
                mode, poet_key = "original", None
                feedback = ["That poet is copyrighted and forbidden — write 100% original couplets instead."]
                continue

            data["poet"] = poet_name
            data["source"] = mode
            data["theme"] = theme
            data["topic"] = theme
            data["tags"] = data.get("tags") or _default_tags(poet_name, mode)
            data["voiceover"] = " ".join(
                (s.get("caption") or "").strip() for s in data["scenes"]
            ).strip()
            logger.info("Script ready (%s/%s, %d scenes, attempt %d)",
                        mode, poet_name, len(data["scenes"]), attempt)
            return data

        logger.warning("Script attempt %d invalid: %s", attempt, issues)
        feedback = issues

    raise RuntimeError(f"Could not produce a valid Urdu script after {MAX_GEN_ATTEMPTS} attempts: "
                        f"{feedback or 'unknown error'} (last raw: {str(last_data)[:200]})")


if __name__ == "__main__":
    print(json.dumps(generate_script("تنہائی"), ensure_ascii=False, indent=2))
