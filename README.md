# Khateb-Ishq — خطبِ عشق 🎙️🧠

Automated **Urdu sad-poetry YouTube Shorts** for a Pakistani audience,
3×/day on GitHub Actions — now powered by **AI-driven performance learning**:

```
📊 Performance Learner → 🎯 Smart Theme Selector → Urdu poetry script (Groq)
→ 🏷️ Hashtag Optimizer → moody AI visuals (9-provider fallback)
→ Pakistani Urdu neural voice (Edge-TTS) → vertical video with proper Naskh RTL captions
→ private upload → YouTube auto-publishes at the PKT peak (publishAt)
→ 💬 Engagement Bot (auto-comments/replies) → 📱 Multi-platform (TikTok/IG/FB)
```

## 🆕 Advanced Features

| Module | What it does |
|---|---|
| 🧠 **Performance Learner** | YouTube Analytics → viral pattern detection → smarter themes |
| 🎯 **Smart Theme Selector** | 5 strategies: trend/performance/competitor/seasonal/catalog |
| 🏷️ **Hashtag Optimizer** | YouTube search trends + competitor analysis → optimal hashtags |
| 🔮 **Trend Predictor** | Autosuggest momentum + seasonal calendar + cultural events |
| 📱 **Multi-Platform Poster** | TikTok, Instagram Reels, Facebook Reels (optional) |
| 💬 **Engagement Bot** | Auto-comments, replies, community posts, polls |

## Daily rhythm (Pakistan time — no DST, so zero cron tricks)

| Run starts | Auto-publishes | Strategy |
|---|---|---|
| 13:30 PKT | **14:00** | Smart (AI-driven) |
| 18:00 PKT | **18:30** | Trend + Performance |
| 21:00 PKT | **21:30** | Seasonal + Competitor hijack |

**Weekly**: Every Monday — full analytics refresh + trend prediction update

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

### Multi-Platform Setup (optional)

1. **TikTok**: Create a TikTok app → get `TIKTOK_ACCESS_TOKEN` + `TIKTOK_OPEN_ID`
2. **Instagram**: Facebook Business account → `IG_ACCESS_TOKEN` + `IG_BUSINESS_ACCOUNT_ID`
3. **Facebook**: Facebook Page → `FB_ACCESS_TOKEN` + `FB_PAGE_ID`
4. Set GitHub Variables: `TIKTOK_ENABLED=true`, `INSTAGRAM_ENABLED=true`, `FACEBOOK_ENABLED=true`

## Tuning

| Env | Default | What it does |
|---|---|---|
| `TOPIC_STRATEGY` | `smart` | `smart` (AI-driven) · `trend` · `performance` · `competitor_hijack` · `seasonal` · `poetry_series` |
| `URDU_VOICE` | `asad` | `asad` (deep male, ideal for gham poetry) · `uzma` (female) · `rotate` |
| `URDU_TTS_RATE` | `-12` | Delivery pace (-25%…+5%); sad poetry wants -10…-15 |
| `POETRY_SOURCE` | `mix` | `mix` · `ghalib` · `iqbal` · `mir` · `original` |
| `PUBLISH_SLOTS` | `10:00,14:00,21:00` | PKT publish peaks (auto-publishAt) |
| `MIN_POST_GAP_HOURS` | `3.0` | Anti-spam minimum gap between posts |
| `PERF_REFRESH_HOURS` | `24` | How often to refresh performance data |
| `VIRAL_MULTIPLIER` | `10` | Views/subs ratio to classify as viral |
| `MAX_HASHTAGS` | `15` | Max hashtags per video |
| `TIKTOK_ENABLED` | `false` | Enable TikTok cross-posting |
| `INSTAGRAM_ENABLED` | `false` | Enable Instagram Reels cross-posting |
| `FACEBOOK_ENABLED` | `false` | Enable Facebook Reels cross-posting |

## Architecture notes

- **Voice**: Edge-TTS `ur-PK-*Neural` voices. Chatterbox/Kokoro here are
  English-language models and would mangle Urdu talaffuz — fatal for poetry.
- **Captions**: Pillow + libraqm shapes RTL Urdu; `fonts-noto`
  (NotoNaskhArabic) is installed in CI. If captions ever look like split
  letters, the runner lost libraqm — see `tests` note.
- **Anti-spam**: 3h minimum gap enforced, fingerprint dedupe, media hash
  per-video dedupe, atomic state commits by `khateb-ishq-bot`.
- **Performance Learner**: YouTube Analytics API → viral pattern detection →
  recommendations fed back into theme selection. Self-learning loop: every
  video makes the next one smarter.
- **Smart Theme Selector**: 5 strategies with weighted selection + automatic
  fallback chain. Replaces `theme_fetcher` with backwards-compatible `get_theme()`.
- **Hashtag Optimizer**: YouTube autosuggest trends + performance-weighted tags
  + mood-specific clusters. Respects YouTube's 15 tags / 500 chars limit.
- **Trend Predictor**: Autosuggest momentum + 12-month seasonal calendar +
  cultural events (Ramadan, Eid, Independence Day, Iqbal Day, etc.).
- **Multi-Platform**: Optional TikTok/Instagram/Facebook posting with
  platform-specific descriptions and hashtags. Non-blocking.
- **Engagement Bot**: Auto-pinned engagement questions, auto-replies to
  positive comments, community post generation, polls.

## New Files

```
src/
├── performance_learner.py    # YouTube Analytics → viral pattern detection
├── hashtag_optimizer.py      # Trend-based hashtag optimization
├── trend_predictor.py        # Future trending topic prediction
├── multi_platform.py         # TikTok/IG/FB auto-posting
├── engagement_bot.py         # Auto-comments, replies, community posts
├── smart_theme_selector.py  # AI-driven theme selection
└── main_advanced.py          # Integrated advanced pipeline

.github/workflows/
├── poetry-short-advanced.yml  # 3x/day pipeline (with analytics)
├── weekly-analytics.yml       # Weekly performance analytics
└── main.yml                   # Updated to use main_advanced.py
```
