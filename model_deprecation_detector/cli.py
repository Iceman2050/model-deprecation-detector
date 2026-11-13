"""Command line interface.

Usage:
    model-deprecation-detector [PATH] [--format text|json|feed]
                               [--today YYYY-MM-DD] [--fail-on retired|deprecated|never]

Exit codes: 0 = nothing at or above the --fail-on severity, 1 = findings at
or above it, 2 = usage / IO error.

Output formats:
- text: human-readable report.
- json: full scan record, including every reference and its locations.
- feed: deprecation notices only, in the ModelMinder feed field schema
  (provider, model_id, status_from, status_to, sunset_date, successor,
  price_change, changelog_url, source_feed) plus file/line locations, so a
  routing table or monitoring system can consume scan results directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from . import __version__
from .lifecycle import classify, load_table
from .scanner import scan

SEVERITY = {"retired": 3, "deprecated": 2, "announced": 1, "listed": 0,
            "no-lifecycle-entry": 0}


def build_report(root: Path, today: date, table: dict) -> dict:
    references, files_scanned = scan(root)
    by_id: dict[tuple[str, str], dict] = {}
    for ref in references:
        key = (ref["provider"], ref["model_id"])
        slot = by_id.setdefault(key, {
            "provider": ref["provider"],
            "model_id": ref["model_id"],
            "locations": [],
        })
        slot["locations"].append({
            "file": ref["file"], "line": ref["line"], "context": ref["context"],
        })
    entries = {e["model_id"]: e for e in table["models"]}
    notices = []
    detailed = []
    for (provider, model_id), slot in sorted(by_id.items()):
        verdict = classify(entries.get(model_id), today)
        detailed.append({**slot, "lifecycle": verdict})
        if verdict["status_to"] in ("retired", "deprecated", "announced"):
            notices.append({
                "provider": provider,
                "model_id": model_id,
                # status_from is the assumed pre-notice state; the scanner
                # cannot observe a provider account's live status.
                "status_from": "active",
                "status_to": verdict["status_to"],
                "sunset_date": verdict["sunset_date"],
                # The vendor's named candidate only. A named successor is
                # NOT a verified safe migration for your workload.
                "successor": verdict["successor"],
                # This tool does not track pricing. Null, never invented.
                "price_change": None,
                "changelog_url": verdict["changelog_url"],
                "source_feed": (
                    f"model-deprecation-detector lifecycle table "
                    f"{table['table_version']} (compiled {table['compiled_on']})"
                ),
                "locations": slot["locations"],
            })
    counts = defaultdict(int)
    for item in detailed:
        counts[item["lifecycle"]["status_to"]] += 1
    return {
        "tool": "model-deprecation-detector",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scan_date": today.isoformat(),
        "root": str(root),
        "files_scanned": files_scanned,
        "lifecycle_table": {
            "version": table["table_version"],
            "compiled_on": table["compiled_on"],
            "sources": table["sources"],
        },
        "summary": {
            "distinct_model_ids": len(detailed),
            "total_references": len(references),
            "retired": counts["retired"],
            "deprecated": counts["deprecated"],
            "announced": counts["announced"],
            "no_lifecycle_entry": counts["no-lifecycle-entry"],
        },
        "notices": notices,
        "references": detailed,
    }


def render_text(report: dict) -> str:
    lines = [
        f"model-deprecation-detector {report['version']} — scan of {report['root']}",
        f"scan date {report['scan_date']} · files scanned {report['files_scanned']} · "
        f"lifecycle table {report['lifecycle_table']['version']} "
        f"(compiled {report['lifecycle_table']['compiled_on']})",
        "",
    ]
    if not report["references"]:
        lines.append("No model references found.")
    for item in report["references"]:
        verdict = item["lifecycle"]
        tag = verdict["status_to"].upper()
        extra = ""
        if verdict["sunset_date"]:
            extra += f" · sunset {verdict['sunset_date']}"
        if verdict["successor"]:
            extra += f" · vendor-named candidate: {verdict['successor']} (unverified migration)"
        lines.append(f"[{tag}] {item['model_id']} ({item['provider']}){extra}")
        for loc in item["locations"]:
            lines.append(f"    {loc['file']}:{loc['line']}  {loc['context']}")
    s = report["summary"]
    lines += [
        "",
        f"Summary: {s['distinct_model_ids']} distinct model ids, "
        f"{s['total_references']} references — retired {s['retired']}, "
        f"deprecated {s['deprecated']}, announced {s['announced']}, "
        f"no lifecycle entry {s['no_lifecycle_entry']}.",
        "Note: 'no lifecycle entry' is not evidence a model is current or supported.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="model-deprecation-detector",
        description="Scan a codebase for LLM model references and flag "
                    "deprecated / retired ids against a dated lifecycle table.",
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Directory to scan (default: current directory)")
    parser.add_argument("--format", choices=("text", "json", "feed"),
                        default="text")
    parser.add_argument("--today", metavar="YYYY-MM-DD",
                        help="Reference date for lifecycle status "
                             "(default: system date). Use for reproducible scans.")
    parser.add_argument("--fail-on", choices=("retired", "deprecated", "never"),
                        default="retired",
                        help="Exit 1 when a finding at this severity exists "
                             "(default: retired)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        print(f"error: invalid --today date: {args.today}", file=sys.stderr)
        return 2

    report = build_report(root.resolve(), today, load_table())
    if args.format == "text":
        print(render_text(report))
    elif args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report["notices"], indent=2))

    if args.fail_on == "never":
        return 0
    threshold = SEVERITY[args.fail_on]
    worst = max((SEVERITY[i["lifecycle"]["status_to"]]
                 for i in report["references"]), default=0)
    return 1 if worst >= threshold and worst > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
