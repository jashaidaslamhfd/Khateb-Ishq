# Khateb-Ishq — خطبِ عشق 🎙️

Automated **Urdu sad-poetry YouTube Shorts** for a Pakistani audience,
3×/day on GitHub Actions:

```
poetry theme (500-catalogue) → Urdu poetry script (Groq Llama 3.3 70B)
→ moody AI visuals (9-provider fallback) → Pakistani Urdu neural voice
(Edge-TTS) → vertical video with proper Naskh RTL captions
→ private upload → YouTube auto-publishes at the PKT peak (publishAt)
```

## Daily rhythm (Pakistan time — no DST, so zero cron tricks)

| Run starts | Auto-publishes |
|---|---|
| 09:00 | **10:00** |
| 13:30 | **14:00** |
| 20:30 | **21:00** (sad-poetry golden hour) |

## Content policy (read before monetizing)

- **Classics (55%)**: couplets by **Ghalib (d.1869), Iqbal (d.1938),
  Mir (d.1810)** — public domain, safe to recite and monetize. `POETRY_SOURCE`
  can pin one poet (`ghalib`/`iqbal`/`mir`).
- **Originals (45%)**: fully AI-written couplets — 100% copyright-free and
  uniquely the channel's identity.
- ⚠️ **Never** recite **Ahmad Faraz (d.2008)** or **Parveen Shakir (d.1994)** —
  still under copyright; using them on a monetized channel can bring strikes.
- Classic episode titles are `Kalam #<n>: <theme>`; spoken CTA and comments
  stay in Urdu.

## Setup (10 minutes)

1. **OAuth for the RIGHT account** — the Urdu channel lives on a *different*
   Google account. On your own PC, logged into that account:
   ```bash
   pip install -r requirements.txt
   python scripts/get_refresh_token.py   # if missing, copy it over from the SKILLOR repo
   ```
   Approve with the account that **owns the Urdu channel**, and if asked,
   pick that channel. Put the printed three values into this repo's secrets.
2. Gh repo → **Settings → Secrets and variables → Actions**:
   `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `REFRESH_TOKEN`
   (optional image keys: `GEMINI_API_KEY`, `HF_API_KEY`, …)
3. **Music**: drop 3–5 copyright-safe sad instrumentals into `assets/music/`
   (see `assets/music/ATTRIBUTION.md`). No tracks = silent background (still fine).
4. Actions → **Run workflow** for a test run; then the 3 crons take over.

## Tuning

| Env | Default | What it does |
|---|---|---|
| `URDU_VOICE` | `asad` | `asad` (deep male, ideal for gham poetry) · `uzma` (female) · `rotate` |
| `URDU_TTS_RATE` | `-12` | Delivery pace (-25%…+5%); sad poetry wants -10…-15 |
| `POETRY_SOURCE` | `mix` | `mix` · `ghalib` · `iqbal` · `mir` · `original` |
| `PUBLISH_SLOTS` | `10:00,14:00,21:00` | PKT publish peaks (auto-publishAt) |
| `MIN_POST_GAP_HOURS` | `3.0` | Anti-spam minimum gap between posts |

## Architecture notes

- **Voice**: Edge-TTS `ur-PK-*Neural` voices. Chatterbox/Kokoro here are
  English-language models and would mangle Urdu talaffuz — fatal for poetry.
- **Captions**: Pillow + libraqm shapes RTL Urdu; `fonts-noto`
  (NotoNaskhArabic) is installed in CI. If captions ever look like split
  letters, the runner lost libraqm — see `tests` note.
- **Anti-spam**: 3h minimum gap enforced, fingerprint dedupe, media hash
  per-video dedupe, atomic state commits by `khateb-ishq-bot`.
- **Roadmap**: self-hosted multilingual voice clone (your own voice),
  daily engagement-question comment like the science channels have.
