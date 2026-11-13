"""Fixture v1 — deliberately mixed model references. Do not 'fix' these;
the expected scan results in ../expected.json depend on them verbatim."""

import os

# Retired 2026-03-26 (OpenAI deprecations page).
PRIMARY_MODEL = "gpt-4-0314"
# Retired 2025-07-21 (Anthropic deprecations page).
LEGACY_MODEL = "claude-2.1"
# Deprecated 2026-10-14, shuts down 2027-01-14.
FALLBACK_MODEL = "gpt-4o"
# Current-generation id with no entry in the bundled lifecycle table.
CURRENT_MODEL = "gpt-5.6-sol"


def current_model():
    # No literal model id here on purpose: resolution is by env var only.
    return os.environ["APP_MODEL"]
