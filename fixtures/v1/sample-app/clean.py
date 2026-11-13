"""Fixture v1 — a file with no literal model ids. The scanner must report
zero references in this file (the model is chosen at deploy time)."""

import os

MODEL = os.environ.get("APP_MODEL", "")
