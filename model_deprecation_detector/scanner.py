"""Static text scan for LLM model-id references.

Detection is pattern-based: a string is reported when it matches a known
provider model-id shape AND contains a version digit (or is a well-known
legacy family name). Detection means "this string looks like a model
reference" — nothing more. The scanner never calls a provider API and never
verifies that an id exists, is callable, or that a replacement is a safe
migration.
"""

from __future__ import annotations

import re
from pathlib import Path

# Provider id shapes. Each pattern must contain a digit in the matched token
# (enforced in _is_model_token) to cut false positives on prose words.
PATTERNS: dict[str, re.Pattern] = {
    "OpenAI": re.compile(
        r"\b(?:gpt-[a-z0-9][a-z0-9.\-]*|o[134](?:-[a-z0-9.\-]+)?|"
        r"text-(?:davinci|curie|babbage|ada)-[0-9a-z\-]+|"
        r"code-davinci-[0-9]+|text-moderation-[0-9a-z]+|"
        r"text-embedding-[a-z0-9\-]+|whisper-[0-9a-z.\-]+|"
        r"tts-1(?:-[a-z]+)?|dall-e-[0-9]+)\b"
    ),
    "Anthropic": re.compile(r"\bclaude-[a-z0-9][a-z0-9.\-]*\b"),
    "Google": re.compile(
        r"\b(?:gemini-[a-z0-9][a-z0-9.\-]*|textembedding-gecko@[0-9]+|"
        r"chat-bison@[0-9]+|text-bison@[0-9]+)\b"
    ),
    "Mistral": re.compile(
        r"\b(?:mistral|open-mistral|open-mixtral|codestral)-[a-z0-9][a-z0-9.\-]*\b"
    ),
    "Cohere": re.compile(r"\bcommand-[a-z0-9][a-z0-9.\-]*\b"),
}

SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".php", ".java",
    ".rs", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".example", ".sample", ".md", ".txt", ".sh", ".tf", ".xml",
}
SCAN_FILENAMES = {".env", ".env.example", ".env.sample", "Dockerfile"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "vendor", "dist", "build"}
# Never scan our own lifecycle data or test expectations: they contain model
# ids by design and would self-flag.
SKIP_FILENAMES = {"lifecycle.json", "expected.json"}
MAX_FILE_BYTES = 2_000_000


def _is_model_token(token: str) -> bool:
    return any(ch.isdigit() for ch in token)


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.name in SKIP_FILENAMES:
            continue
        if path.name in SCAN_FILENAMES or path.suffix.lower() in SCAN_EXTENSIONS:
            yield path


def scan(root: Path) -> tuple[list[dict], int]:
    """Return (references, files_scanned). Each reference: provider,
    model_id, file (relative), line, context (trimmed line text)."""
    references: list[dict] = []
    files_scanned = 0
    for path in iter_files(root):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_scanned += 1
        rel = str(path.relative_to(root)) if path != root else path.name
        for lineno, line in enumerate(text.splitlines(), start=1):
            for provider, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    token = match.group(0).rstrip(".-")
                    if not _is_model_token(token):
                        continue
                    references.append({
                        "provider": provider,
                        "model_id": token,
                        "file": rel,
                        "line": lineno,
                        "context": line.strip()[:200],
                    })
    references.sort(key=lambda r: (r["file"], r["line"], r["model_id"]))
    return references, files_scanned
