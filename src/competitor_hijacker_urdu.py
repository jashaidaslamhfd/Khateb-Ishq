import json
import os
import re
import urllib.parse
import urllib.request
import logging
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
THEMES_PATH = ROOT / "data" / "poetry_themes.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("competitor_hijacker_urdu")

# Emotional, poetic, and classic keywords in Urdu/Roman-Urdu for relevance checking
POETRY_KEYWORDS = {
    "juda", "juda'i", "muhabbat", "ishq", "dard", "tanhai", "gham", "shiri", "ghamgin",
    "ghalib", "iqbal", "mir", "shayar", "shayari", "ghazal", "status", "poetry",
    "raat", "rain", "barish", "ashk", "aansu", "dil", "yaad", "yaadein", "zindagi",
    # Channel's top search terms (real analytics 2026-08-01)
    "background music", "bg music", "copyright free", "no copyright",
    "sad background", "poetry background",
}

def fetch_youtube_autosuggest_ur(seed: str) -> list[str]:
    """
    Scrapes Google's public YouTube autosuggest endpoint to find real-time 
    high-demand poetry and shayari searches in Urdu/Hindi.
    """
    try:
        encoded_seed = urllib.parse.quote(seed)
        url = f"http://suggestqueries.google.com/complete/search?client=youtube&hl=ur&ds=yt&q={encoded_seed}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8", "ignore")
            queries = re.findall(r'"([^"]*)"', content)
            suggestions = [q for q in queries if q.lower() != seed.lower() and len(q) > len(seed)]
            return list(dict.fromkeys(suggestions))
    except Exception as exc:
        logger.warning(f"YouTube Urdu autosuggest fetch failed for seed '{seed}': {exc}")
        return []

def score_topic_ur(topic: str, source: str, views: int = 0) -> dict:
    """
    Scores a candidate Urdu poetry / motivational topic on relevance and emotional density.
    """
    score = 50 # Base score
    lowered = topic.lower()
    
    # 1. Poetic Relevance checking (Urdu / Roman Urdu keywords)
    matches = sum(1 for kw in POETRY_KEYWORDS if kw in lowered)
    score += min(matches * 15, 30) # Max 30 points for keyword density
    
    # 2. Structural/Aesthetic quality
    if "status" in lowered or "poetry" in lowered or "shayari" in lowered:
        score += 15
    if "sad" in lowered or "emotional" in lowered or "motivational" in lowered:
        score += 10
        
    return {
        "topic": topic,
        "title": topic,
        "source": source,
        "score": min(score, 100),
        "views": views
    }

def get_hijacked_viral_topic_ur(exclude_list: list[str] = None) -> dict:
    """
    Orchestrates the selection of real-time South Asian trending poetry themes:
    1. Scrapes YouTube autosuggest for popular poetry/shayari searches.
    2. Scores candidates on emotional resonance and search intent.
    3. Selects the best performing poetic concept.
    """
    exclude_list = exclude_list or []
    normalized_excludes = [t.lower().strip() for t in exclude_list]
    
    candidates = []
    
    # --- Step 1: Real-time Autosuggest (Urdu/Shayari seeds) ---
    logger.info("Step 1/3: Harvesting real-time Urdu poetry search trends...")
    seeds = ["poetry background music", "sad shayari background music", "background music for poetry",
             "background music poetry", "poetry bg music", "sad background music",
             "copyright free background music", "no copyright music",
             "urdu poetry sad", "ghalib poetry"]
    for seed in seeds:
        suggestions = fetch_youtube_autosuggest_ur(seed)
        for sug in suggestions:
            topic_title = sug.capitalize()
            candidates.append(score_topic_ur(topic_title, "youtube_autosuggest_ur"))
            
    # --- Step 2: Fallback & Catalog Blending ---
    logger.info("Step 2/3: Analyzing Urdu poetry catalog themes...")
    if THEMES_PATH.exists():
        try:
            with open(THEMES_PATH, "r", encoding="utf-8") as f:
                themes = json.load(f)
            for t in themes[:30]: # Select 30 classic themes to blend
                theme_str = t.get("theme", "")
                candidates.append(score_topic_ur(theme_str, "poetry_series_fr", 2000000))
        except Exception as exc:
            logger.warning(f"Error loading catalog themes: {exc}")
            
    # --- Step 3: Filtering, Deduplicating, and Selection ---
    logger.info("Step 3/3: Evaluating, filtering and selecting the ultimate poetic winner...")
    
    relevant_candidates = []
    seen = set()
    for cand in candidates:
        topic_normalized = cand["topic"].lower().strip()
        if (topic_normalized not in seen and 
            topic_normalized not in normalized_excludes and 
            any(kw in topic_normalized for kw in POETRY_KEYWORDS)):
            seen.add(topic_normalized)
            relevant_candidates.append(cand)
            
    if not relevant_candidates:
        # Fallback to standard romantic poetry
        fallback_topic = "ghamgin juda'i — raat ke do bajay"
        logger.warning(f"No suitable dynamic Urdu candidates; falling back to: {fallback_topic}")
        return score_topic_ur(fallback_topic, "viral_hijack_fallback_ur", 1200000)
        
    # Sort by score
    relevant_candidates.sort(key=lambda x: -x["score"])
    
    # Pick from top 5 candidates
    top_candidates = relevant_candidates[:5]
    import random
    winner = random.choice(top_candidates)
    
    logger.info(f"🏆 Urdu Winner Chosen: '{winner['topic']}' | Source: {winner['source']} | Score: {winner['score']}/100")
    
    return winner
