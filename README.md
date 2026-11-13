# model-deprecation-detector

Scan a codebase for LLM model references, and flag the ones whose vendor has
already deprecated or retired them — before they break in production.

## The problem

Model ids are strings. They sit in source files, YAML configs, `.env`
examples, Terraform, docs and runbooks, and nothing about the string changes
when the vendor retires the model behind it. The failure only shows up
later, as a 404 from a model that used to work — usually after a release,
not before it. Teams discover their exposure by accident.

This tool makes the exposure explicit and reviewable: it statically scans a
repository, lists every recognised model reference with its file and line,
and checks each id against a dated, sourced lifecycle table bundled in the
repo.

## What it does

- Detects model-id references for **OpenAI, Anthropic and Google** (with a
  lifecycle table), plus **Mistral and Cohere id shapes** (detected and
  reported, but with no lifecycle verdict — see Limitations).
- Classifies each id against the bundled lifecycle table
  (`model_deprecation_detector/data/lifecycle.json`, version `2026.11.0`,
  compiled 2026-11-13 from the vendors' official deprecation pages):
  `retired`, `deprecated`, `announced`, or `no-lifecycle-entry`.
- Emits three formats: a human-readable text report, a full JSON scan
  record, and a **feed format** — deprecation notices in the ModelMinder
  feed field schema (`provider`, `model_id`, `status_from`, `status_to`,
  `sunset_date`, `successor`, `price_change`, `changelog_url`,
  `source_feed`) plus file/line locations, so a monitoring system or a
  routing table can consume scan results directly.
- Suggests the vendor's own named replacement candidate where the vendor
  published one. **A named successor is not a verified migration** — see
  verdict honesty below.

## Verdict honesty

- Detection is pattern matching. A reported string *looks like* a model
  reference; the tool never calls a provider API and never verifies that an
  id exists, is enabled on your account, or behaves like the old one.
- `no-lifecycle-entry` means "not in the bundled table". It is **not**
  evidence that a model is current, supported, or safe.
- `successor` is the replacement the *vendor* named in its deprecation
  notice. Whether it is a safe migration for your workload — prompts, tool
  schemas, evals, cost — is a separate verification this tool does not do.
  That verification loop is what [ModelMinder](https://modelminder.getingeniousai.com)
  is built for; this scanner is the standalone, no-account front end of the
  same idea.
- `price_change` in feed output is always `null`. This tool does not track
  pricing and never invents a value.
- The lifecycle table is a snapshot. Vendors revise dates; the table records
  its compile date and every entry's source URL so you can re-verify before
  acting.

## Exact supported scope

- **Files scanned:** source and config text files (`.py .js .ts .tsx .jsx
  .go .rb .php .java .rs .json .yaml .yml .toml .ini .cfg .env .example
  .sample .md .txt .sh .tf .xml`, plus bare `.env*` filenames and
  `Dockerfile`), under 2 MB each, skipping `.git`, `node_modules`,
  virtualenvs, `vendor`, `dist`, `build`.
- **Not scanned:** binaries, archives, images, compiled output; model ids
  constructed at runtime (string concatenation, f-string fragments, ids
  fetched from a remote config) are invisible to a static scan.
- **Lifecycle coverage:** 40 model ids with published vendor deprecation or
  retirement notices (OpenAI 17, Anthropic 13, Google 10), compiled
  2026-11-13. Ids without a captured notice get no verdict.
- **Runtime:** Python ≥ 3.9, standard library only. No network access.

## Install and use

```bash
git clone https://github.com/Iceman2050/model-deprecation-detector
cd model-deprecation-detector
pip install .            # or just run it in place, no install needed:

python -m model_deprecation_detector /path/to/your/repo
python -m model_deprecation_detector /path/to/your/repo --format json
python -m model_deprecation_detector /path/to/your/repo --format feed
```

Options:

- `--today YYYY-MM-DD` — pin the reference date (reproducible scans, CI
  baselines, tests). Default: the system date.
- `--fail-on retired|deprecated|never` — exit-code gate for CI. Default
  `retired`: exit `1` when a retired id is present, `0` otherwise, `2` on
  usage/IO error.

## Reproduce the verified result

The repo ships a versioned fixture with planted references
(`fixtures/v1/sample-app/`) and its expected results
(`fixtures/v1/expected.json`):

```bash
python -m model_deprecation_detector fixtures/v1/sample-app --today 2026-11-13
python -m unittest discover -s tests -v
```

Expected behaviour at the pinned date (lifecycle table `2026.11.0`):
9 distinct model ids in 5 files — 5 retired (`gpt-4-0314`, `claude-2.1`,
`gemini-1.5-flash`, `text-davinci-003`, `claude-instant-1.2`), 2 deprecated
(`gpt-4o`, `claude-sonnet-4-5-20250929`), 2 with no lifecycle entry
(`gpt-5.6-sol`, `gemini-2.5-flash`); exit code `1`.

## Actual test results

Run on 2026-11-13, Python 3, from a clean checkout of this repo:

```
$ python -m unittest discover -s tests -v
...
Ran 15 tests in 0.018s

OK
```

```
$ python -m model_deprecation_detector fixtures/v1/sample-app --today 2026-11-13
[RETIRED]    claude-2.1 (Anthropic) · sunset 2025-07-21 · vendor-named candidate: claude-opus-4-8 (unverified migration)
[RETIRED]    claude-instant-1.2 (Anthropic) · sunset 2024-11-06
[DEPRECATED] claude-sonnet-4-5-20250929 (Anthropic) · sunset 2026-11-30
[RETIRED]    gemini-1.5-flash (Google) · sunset 2025-09-29
[NO-LIFECYCLE-ENTRY] gemini-2.5-flash (Google)
[RETIRED]    gpt-4-0314 (OpenAI) · sunset 2026-03-26
[DEPRECATED] gpt-4o (OpenAI) · sunset 2027-01-14
[NO-LIFECYCLE-ENTRY] gpt-5.6-sol (OpenAI)
[RETIRED]    text-davinci-003 (OpenAI) · sunset 2024-01-04
Summary: 9 distinct model ids, 9 references — retired 5, deprecated 2, announced 0, no lifecycle entry 2.
(exit code 1)
```

These are real outputs of the commands above, not illustrations. The unit
tests assert the fixture scan matches `fixtures/v1/expected.json` exactly,
including that every reported line number actually contains the reported id.

## Updating the lifecycle table

`model_deprecation_detector/data/lifecycle.json` is hand-maintained data.
To update it: read the vendor pages listed in its `sources`, add or adjust
entries with the vendor's dates and named replacements, bump
`table_version`, set `compiled_on`, and update `fixtures/*/expected.json` +
the tests in the same commit. Never add an entry you cannot point to a
vendor source for.

## Limitations

- Static, pattern-based detection: false positives are possible in prose
  (docs are scanned deliberately — runbooks carry stale ids too) and false
  negatives are certain for runtime-constructed ids.
- The table covers the notices captured at compile time for three vendors.
  Mistral and Cohere ids are detected but receive no lifecycle verdict, and
  other providers (AWS Bedrock, Azure OpenAI, DeepSeek, xAI, open-weight
  hosts) are out of scope for v0.1.0.
- Lifecycle status can differ per platform (e.g. Bedrock vs the vendor's own
  API set different retirement schedules). Verdicts here follow the vendor's
  own API documentation.
- Dates are the vendor's published dates at compile time; vendors have
  moved dates before and will again.

## Relationship to ModelMinder

This scanner finds the references once, locally, for free. Continuous
monitoring — a maintained lifecycle catalog, change alerts when a vendor
moves a date, and migration evaluation against your actual usage — is
[ModelMinder](https://modelminder.getingeniousai.com). The `--format feed`
output uses ModelMinder's notice schema on purpose, so scan results can be
tested against a routing table or fed into a monitoring workflow without
translation.

## License

MIT. Built by Ingenious AI — https://getingeniousai.com

## Ingenious AI platforms

Built by Ingenious AI. The fleet — every platform does one job:

- [Agent Auth Gateway](https://authgateway.getingeniousai.com) · [MandateGuard](https://mandateguard.getingeniousai.com) · [Agentic Receipts](https://agentic-receipts.getingeniousai.com) · [Agent Flight Recorder](https://flightrecorder.getingeniousai.com) · [TrustGate](https://trustgate.getingeniousai.com) · [BoundaryVault](https://boundaryvault.getingeniousai.com) · [Rogue-Agent Defense](https://rogue-defense.getingeniousai.com) · [AgentGate](https://agentgate.getingeniousai.com) · [Agent Passport](https://agentpassport.getingeniousai.com) · [HomeShield](https://homeshield.getingeniousai.com) · [AgentBlock](https://agentblock.getingeniousai.com) · [ChatBreaker](https://chatbreaker.getingeniousai.com) · [EvalScope](https://evalscope.getingeniousai.com) · [CompanionGuard](https://companionguard.getingeniousai.com)
- [DomainGuard](https://domainguard.getingeniousai.com) · [BreachHunter](https://breachhunter.getingeniousai.com) · [TakedownCoop](https://takedowncoop.getingeniousai.com) · [WireWatch](https://wirewatch.getingeniousai.com) · [CallbackShield](https://callbackshield.getingeniousai.com) · [Vibe-Code Audit](https://vibe-audit.getingeniousai.com)
- [DisclosureGuard](https://disclosureguard.getingeniousai.com) · [ProvenanceGuard](https://provenanceguard.getingeniousai.com) · [ADMT](https://admt.getingeniousai.com) · [ReviewDesk](https://reviewdesk.getingeniousai.com) · [CRAClock](https://craclock.getingeniousai.com) · [AI Audit Exchange](https://auditexchange.getingeniousai.com) · [TermsWatch](https://termswatch.getingeniousai.com) · [ModelMinder](https://modelminder.getingeniousai.com) · [ReviewProof](https://reviewproof.getingeniousai.com) · [EInvoice](https://einvoice.getingeniousai.com) · [DueLadder](https://dueladder.getingeniousai.com) · [OutcomeMeter](https://outcomemeter.getingeniousai.com)
- [AgentReady](https://agentready.getingeniousai.com) · [Store Audit](https://storeaudit.getingeniousai.com) · [ContentCraft AI](https://contentcraft.getingeniousai.com) · [GEOFixer](https://geofixer.getingeniousai.com)
- Full directory: https://getingeniousai.com/platforms
