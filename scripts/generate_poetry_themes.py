#!/usr/bin/env python3
"""Generate data/poetry_themes.json — 500 unique poetry themes.

Matrix-generated: subject × mood × setting, culturally grounded for an
Urdu sad-poetry audience. run once (CI also runs it to keep the file fresh):
    python scripts/generate_poetry_themes.py
"""

import json
import os

SUBJECTS = [
    "juda'i", "tanha'i", "intezaar", "yaadein", "khwaab", "gham", "hijr",
    "wafa", "dard", "sukoon", "umeed", "khamoshi", "dua", "safar", "maut",
    "zindagi", "waqt", "mazi", "mohabbat", "aashiqui", "sheher", "raat",
    "barsaat", "chand", "sooraj", "khushbu", "chitthi", "aina", "raaz",
    "iktifa",
]
MOODS = ["aahista", "be-sahara", "gila-shikwa", "khafa", "shafaq-posh",
         "viran", "narm", "gehra", "be-khabar", "majrooh"]
SETTINGS = ["raat ke do bajay", "barsati sham mein", "purani kitab ke sahaano mein",
            "khaali kamray mein", "musafir ki raah par", "sheher ki bheer mein",
            "sheeshey ke paas", "chhat ke kinaaray", "band darwaazay ke peechay",
            "sooraj dhaltay waqt"]

themes = []
seen = set()
for subject in SUBJECTS:
    for mood in MOODS:
        for setting in SETTINGS[:2]:  # cap matrix to stay near 500
            theme = f"{mood} {subject} — {setting}"
            if theme not in seen:
                seen.add(theme)
                themes.append({
                    "series_number": len(themes) + 1,
                    "series_title": f"Kalam #{len(themes)+1}: {subject.title()}",
                    "theme": theme,
                })
if len(themes) > 500:
    themes = themes[:500]

os.makedirs("data", exist_ok=True)
with open("data/poetry_themes.json", "w", encoding="utf-8") as fh:
    json.dump(themes, fh, ensure_ascii=False, indent=1)
print(f"Wrote data/poetry_themes.json with {len(themes)} unique themes")
