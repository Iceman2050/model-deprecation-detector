# Changelog

## 0.1.0 — 2026-11-13

- Initial release. Static scanner for OpenAI / Anthropic / Google model-id
  references (Mistral / Cohere id shapes detected without lifecycle
  verdicts), text + JSON + ModelMinder-schema feed output, CI exit-code
  gating, `--today` pinning for reproducible scans.
- Lifecycle table `2026.11.0`: 40 vendor-noticed model ids compiled
  2026-11-13 from the official OpenAI, Anthropic and Google deprecation
  pages (plus the ModelMinder live feed for the gpt-4-0613 notice).
- Fixtures v1 with planted references + expected results; 15 unit tests,
  all passing at release.
