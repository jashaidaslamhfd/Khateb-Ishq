"""Temporary: verify MODELSLAB_API_KEY works and music_generator succeeds."""
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

import music_generator  # noqa: E402

print("KEY present:", bool(os.environ.get("MODELSLAB_API_KEY", "").strip()))
print("PROMPT:", music_generator._make_prompt("dard bhari"))

out = music_generator.generate_sad_music(theme="dard bhari", duration=55)
print("RESULT:", out)
sys.exit(0 if out else 1)
