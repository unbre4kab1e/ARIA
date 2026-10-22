import os
import sys
from pathlib import Path

# Tests run without real Gemini credentials or a real browser.
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
