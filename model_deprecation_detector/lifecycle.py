"""Load the bundled, dated lifecycle table and classify model ids against it.

The table is data, not truth: it is a snapshot compiled on the date recorded
inside the JSON file, from the vendor deprecation pages listed in its
``sources`` array. Statuses are computed against a reference date so scans
are reproducible (``--today``) and testable.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "lifecycle.json"


def load_table(path: Path | None = None) -> dict:
    with open(path or DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def classify(entry: dict | None, today: date) -> dict:
    """Return a lifecycle verdict for one lifecycle-table entry (or None).

    Verdicts:
    - ``retired``: the vendor shutdown/retirement date has passed.
    - ``deprecated``: deprecation was announced and the shutdown date is
      still in the future (or none is published yet).
    - ``announced``: an entry exists but neither date has been reached.
    - ``no-lifecycle-entry``: the id was recognised as a model reference but
      is absent from the bundled table. Absence is NOT evidence that the
      model is current, supported, or safe to migrate to.
    """
    if entry is None:
        return {
            "status_to": "no-lifecycle-entry",
            "sunset_date": None,
            "successor": None,
            "replacement_candidates": [],
            "changelog_url": None,
        }
    shutdown = entry.get("shutdown_date")
    deprecated = entry.get("deprecated_date")
    candidates = entry.get("replacement_candidates") or []
    if shutdown and today >= date.fromisoformat(shutdown):
        status = "retired"
    elif deprecated and today >= date.fromisoformat(deprecated):
        status = "deprecated"
    elif shutdown or deprecated:
        status = "announced"
    else:
        status = "listed"
    return {
        "status_to": status,
        "sunset_date": shutdown,
        "successor": candidates[0] if candidates else None,
        "replacement_candidates": candidates,
        "changelog_url": entry.get("source_url"),
    }
