#!/usr/bin/env python3
"""Thumbnail A/B Generator — Generate multiple thumbnail variants for A/B testing.

2026 MUST-HAVE: Top channels test 3-5 thumbnails per video. YouTube's own data
shows that the right thumbnail can increase CTR by 30-50%. Without A/B testing,
you're guessing what works. This module generates multiple thumbnail variants
with different styles, text positions, and colors.

Features:
  1. Generate 3 thumbnail variants per video
  2. Different text positions (top, center, bottom)
  3. Different color schemes (warm, cool, dark)
  4. Different font sizes (large, medium, small)
  5. Safe-zone awareness (not covering Shorts UI elements)
  6. Auto-select best based on channel performance data

Usage:
  from thumbnail_ab import ThumbnailABGenerator
  gen = ThumbnailABGenerator()
  variants = gen.generate_variants(first_image, title, hook_roman)
  # variants = ["output/thumb_a.jpg", "output/thumb_b.jpg", "output/thumb_c.jpg"]
"""

import logging
import os
import random
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("thumbnail_ab")

WIDTH, HEIGHT = 1080, 1920

# ── Thumbnail style presets ─────────────────────────────────────────────────
THUMBNAIL_STYLES = {
    "warm_dark": {
        "overlay_color": (0, 0, 0, 180),
        "text_color": (255, 230, 100),  # Gold/yellow
        "stroke_color": (0, 0, 0, 230),
        "vignette_strength": 0.5,
        "text_position": "center",
        "font_size": 64,
    },
    "cool_blue": {
        "overlay_color": (0, 20, 60, 170),
        "text_color": (200, 220, 255),
        "stroke_color": (0, 0, 0, 220),
        "vignette_strength": 0.4,
        "text_position": "bottom",
        "font_size": 56,
    },
    "high_contrast": {
        "overlay_color": (0, 0, 0, 200),
        "text_color": (255, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "vignette_strength": 0.6,
        "text_position": "top",
        "font_size": 72,
    },
}

# ── Latin font candidates ──────────────────────────────────────────────────
_LATIN_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "assets/fonts/DejaVuSans-Bold.ttf",
]


class ThumbnailABGenerator:
    """Generate multiple thumbnail variants for A/B testing."""

    def __init__(self):
        self.font = self._load_font(64)

    def _load_font(self, size: int):
        """Load the best available Latin font."""
        for path in _LATIN_FONT_CANDIDATES:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        logger.warning("No Latin font found — using default bitmap font")
        return ImageFont.load_default()

    def _apply_vignette(self, img: Image.Image, strength: float = 0.5) -> Image.Image:
        """Apply vignette effect to image."""
        arr = np.asarray(img).astype(np.float32)
        yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
        d = np.sqrt(((xx - WIDTH / 2) / (WIDTH / 2)) ** 2 +
                     ((yy - HEIGHT / 2) / (HEIGHT / 2)) ** 2)
        vig = (1.0 - strength * np.clip(d - 0.5, 0, 1) ** 1.5).astype(np.float32)
        arr *= vig[..., None]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    def _apply_grade(self, img: Image.Image, style: str = "warm") -> Image.Image:
        """Apply color grading to image."""
        arr = np.asarray(img).astype(np.float32)
        if style == "warm":
            arr[..., 0] *= 1.08  # Warm highlights
            arr[..., 2] *= 0.92  # Cool shadows
        elif style == "cool":
            arr[..., 0] *= 0.92
            arr[..., 2] *= 1.08
        elif style == "high_contrast":
            arr = (arr - 128.0) * 1.15 + 128.0
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    def _add_text_overlay(self, img: Image.Image, text: str, style: dict) -> Image.Image:
        """Add styled text overlay to image."""
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Load font at style's size
        font = self._load_font(style.get("font_size", 64))

        # Wrap text
        is_roman = not any("\u0600" <= ch <= "\u06FF" for ch in text)
        if is_roman:
            lines = textwrap.wrap(text, 24)
        else:
            lines = textwrap.wrap(text, 22)

        line_h = int(style.get("font_size", 64) * 1.2)
        box_h = line_h * len(lines) + 60
        text_color = style.get("text_color", (255, 255, 255, 255))
        stroke_color = style.get("stroke_color", (0, 0, 0, 230))
        overlay_color = style.get("overlay_color", (0, 0, 0, 180))

        # Position
        position = style.get("text_position", "center")
        if position == "top":
            y0 = 200
        elif position == "bottom":
            y0 = HEIGHT - box_h - 200
        else:  # center
            y0 = (HEIGHT - box_h) // 2

        # Draw background strip
        draw.rounded_rectangle([40, y0, WIDTH - 40, y0 + box_h],
                              radius=30, fill=overlay_color)

        # Draw text
        y = y0 + 30
        for line in lines:
            w = draw.textlength(line, font=font)
            draw.text(((WIDTH - w) / 2, y), line, font=font,
                     fill=text_color,
                     stroke_width=3, stroke_fill=stroke_color)
            y += line_h

        # Composite
        out = img.convert("RGBA")
        out.alpha_composite(overlay)
        return out.convert("RGB")

    def _add_hook_badge(self, img: Image.Image, hook_text: str) -> Image.Image:
        """Add a small 'hook' badge at the top of the thumbnail.
        
        This is what makes viewers STOP scrolling — a bold emotional
        statement in the top 1/3 of the thumbnail.
        """
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        if not hook_text:
            return img

        font = self._load_font(42)
        lines = textwrap.wrap(hook_text, 28)
        line_h = 52
        box_h = line_h * len(lines) + 40

        # Red/orange badge at top
        draw.rounded_rectangle([60, 120, WIDTH - 60, 120 + box_h],
                              radius=20, fill=(180, 30, 30, 200))

        y = 140
        for line in lines:
            w = draw.textlength(line, font=font)
            draw.text(((WIDTH - w) / 2, y), line, font=font,
                     fill=(255, 255, 255, 255),
                     stroke_width=2, stroke_fill=(0, 0, 0, 200))
            y += line_h

        out = img.convert("RGBA")
        out.alpha_composite(overlay)
        return out.convert("RGB")

    def generate_variants(self, first_image: str, title: str,
                          hook_roman: str = None, count: int = 3) -> List[str]:
        """Generate multiple thumbnail variants for A/B testing.

        Args:
            first_image: Path to the first scene image
            title: Video title (Roman Urdu preferred)
            hook_roman: Roman Urdu hook text (shown as badge)
            count: Number of variants to generate (2-5)

        Returns:
            List of paths to generated thumbnail variants
        """
        if not os.path.exists(first_image):
            logger.warning("Image not found: %s — generating placeholder", first_image)
            img = Image.new("RGB", (WIDTH, HEIGHT), (8, 8, 12))
        else:
            img = Image.open(first_image).convert("RGB")
            # Resize to 1080x1920
            sw, sh = img.size
            scale = max(WIDTH / sw, HEIGHT / sh)
            img = img.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
            nw, nh = img.size
            img = img.crop(((nw - WIDTH) // 2, (nh - HEIGHT) // 2,
                           (nw + WIDTH) // 2, (nh + HEIGHT) // 2))

        os.makedirs("output/thumbnails", exist_ok=True)

        variants = []
        style_names = list(THUMBNAIL_STYLES.keys())
        grade_styles = ["warm", "cool", "high_contrast"]

        for i in range(min(count, 5)):
            style_name = style_names[i % len(style_names)]
            style = THUMBNAIL_STYLES[style_name]
            grade = grade_styles[i % len(grade_styles)]

            # Apply processing
            variant = img.copy()
            variant = self._apply_grade(variant, grade)
            variant = self._apply_vignette(variant, style.get("vignette_strength", 0.5))
            variant = self._add_text_overlay(variant, title, style)

            # Add hook badge on first variant only
            if i == 0 and hook_roman:
                variant = self._add_hook_badge(variant, hook_roman)

            # Save
            path = f"output/thumbnails/thumb_{chr(97 + i)}.jpg"
            variant.save(path, quality=90)
            variants.append(path)

            logger.info("Thumbnail variant %c: %s (style: %s, grade: %s)",
                       chr(97 + i), path, style_name, grade)

        return variants

    def select_best(self, variants: List[str]) -> str:
        """Select the best thumbnail based on channel performance data.
        
        Currently uses a simple heuristic: warm + high contrast thumbnails
        tend to perform best for sad poetry channels. In the future, this
        could use A/B test results from YouTube Analytics.
        """
        if not variants:
            return None

        # For now, prefer the first variant (warm_dark + hook badge)
        # This is the most eye-catching for sad poetry channels
        return variants[0]


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    gen = ThumbnailABGenerator()
    # Test with a placeholder image
    test_img = Image.new("RGB", (WIDTH, HEIGHT), (20, 15, 30))
    test_path = "output/test_scene.jpg"
    os.makedirs("output", exist_ok=True)
    test_img.save(test_path)

    variants = gen.generate_variants(
        test_path,
        title="Gham-e-Dil | Sad Urdu Poetry | Background Music",
        hook_roman="Jab apna bana hua bhi paraya lage...",
    )

    print(f"\n🖼️ Generated {len(variants)} thumbnail variants:")
    for v in variants:
        print(f"  {v}")
