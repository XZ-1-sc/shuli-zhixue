"""Vercel Python Function entry point for the existing FastAPI application."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Vercel serves the Vue build from its CDN. Keep FastAPI focused on API routes.
os.environ.setdefault("STATIC_DIR", "")

from app.main import app  # noqa: E402,F401
