# Discovery Engine

> Discover exceptional companies before they become widely recognized.

Discovery Engine is a modular Python platform that analyzes the North American equity universe and produces a transparent, explainable **Discovery Score** to prioritize research opportunities.

## Current Status

**Version:** v0.3 Intelligence — Sprint 5 in progress

The project now applies an explainable metadata pre-filter, persistent cache,
bounded concurrent collection, transient retry/backoff, and resumable runs.
Provider calls are globally paced, and partial runs can retry unresolved errors.
The release was validated across all 6,424 configured North American listings
with zero provider or pipeline errors.

v0.3 is introducing structural asset classification, explainable factor
results, score confidence, enhanced financial signals, and research reporting.
Fundamental factors currently run in shadow mode so their coverage and score
distributions can be validated before ranking weights change. Valuation and
risk factors follow explicit data-quality rules: stale and invalid inputs do
not score, while usable undated inputs reduce confidence.

## Core Principles

- Discovery over prediction
- Transparency over black boxes
- Configuration over hardcoding
- Modular architecture
- Explainable scoring

## Running

Run the complete configured universe:

```powershell
python main.py
```

Run a controlled smoke test by ticker or universe size:

```powershell
python main.py --tickers DCBO.TO WELL.TO SOFI IONQ RKLB
python main.py --limit 25
python main.py --balanced-sample 200
```

Each completed run exports a full diagnostic report, a curated top-candidate
report, and JSON coverage analytics. Balanced samples deterministically
interleave Canadian and U.S. listings for representative validation.

Runs also export an officially ordered calibration CSV and a JSON calibration
summary. These include relative percentiles, factor distributions, rank
correlation, top-list overlap, outliers, low-confidence flags, and experimental
blend scenarios. Experimental ranks never change the official candidate order.

Calibration treats extreme inputs through configurable cap/invalid rules,
removes sector-inappropriate factors from the applicable scoring denominator,
and requires sufficient fundamental confidence before a company enters a
blended scenario. Original provider values remain visible for audit.

Coverage-neutral calibration selects only factors with adequate data in both
Canada and the United States. Technical scoring defines the candidate pool;
fundamentals compare companies with suitable peers and can reorder only within
bounded technical bands. Configurable gates reject scenarios that create
country bias, excessive movement, or insufficient top-list retention.

Completed runs can be recalibrated without Yahoo or any other provider call:

```powershell
python main.py --recalibrate-run RUN_ID
```

The command rebuilds calibration artifacts, exports decision-ready research
queues for every passing weighted scenario, creates a combined top-25 review,
summarizes country and sector composition, and records provenance in the
original run manifest. It fails safely when a run is incomplete or its
checkpoints cannot be reconstructed losslessly.

Passing weighted scenarios are compared before one controls the v0.3 research
queue. The comparison exports consensus rank, rank sensitivity, and candidate
agreement at several cutoffs. The configured 80% technical / 20% fundamental
scenario is selected only while it passes every calibration gate; the original
Discovery Score and official technical report remain unchanged.

Deterministic research packets can be generated from a completed run without
network or AI calls:

```powershell
python main.py --research-run RUN_ID --top 10
```

The command uses the selected passing research scenario and exports JSON and
Markdown containing identity, technical signals, core fundamental evidence,
peer context, data-quality notes, and research questions. AI synthesis is
disabled by default. The provider boundary, prompt versioning, response cache,
and per-company failure isolation are present for optional sourced synthesis;
neither packets nor future AI output can modify ranking.

Primary-source evidence collection is a separate, explicit network action:

```powershell
$env:SEC_USER_AGENT = "Discovery Engine your-email@example.com"
python main.py --research-run RUN_ID --top 10 --collect-sources
```

The collector retrieves recent SEC filings for U.S. candidates, conservatively
paces requests, caches raw responses for seven days, and records publisher,
URL, dates, source type, priority, and SHA-256 hash. Unsupported companies and
source failures remain visible per candidate. A reviewed local manifest can
add approved sources with `--source-manifest PATH`; its domains must first be
allowlisted in `config/settings.json`. Terminal and manifest summaries report
evidence documents, failures, cache hits, misses, expiry, and read errors. AI
synthesis remains disabled.

Validated cited synthesis is an additional opt-in action. First set
`research.ai_synthesis_enabled` to `true` in `config/settings.json`, then keep
the API key and SEC contact identity only in the local terminal environment:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:SEC_USER_AGENT = "Discovery Engine your-email@example.com"
python main.py --research-run RUN_ID --top 5 --collect-sources --synthesize
```

The OpenAI Responses API receives bounded evidence excerpts and returns a
strict JSON-schema research brief. Sourced facts must cite an attached URL and
SHA-256 hash; interpretations are labeled separately. Unsupported citations,
uncited sourced facts, refusals, and malformed outputs fail only that company.
Validated responses are cached by packet, evidence hashes, prompt version,
provider, and model. The API request disables response storage. Readable briefs
and structured validation metrics are exported without changing any score or
rank. Candidates without evidence are skipped and do not trigger an AI call.

Audit the latest saved research artifact without SEC or AI calls:

```powershell
python main.py --audit-research RUN_ID
```

This exports automated evidence, synthesis, citation, section-completeness,
error, sourced-evidence-use, and ranking-integrity gates plus a claim-level
triage artifact and a risk-based `research_human_review` CSV. Material
interpretations always require review; other interpretations plus sourced
risk, numeric, material, and citation-complexity claims receive elevated
sampling priority. Lower-risk claims are selected by a deterministic configured
sample, with at least one claim retained from every populated candidate
section. Stable claim IDs bind the saved audit to
the exact review queue, so removing or duplicating sampled rows blocks
finalization. Automated success produces only
`pending_human_review`. Reviewers must mark every row's `accuracy_review` and
`citation_support_review` as `pass` or `fail`, and `human_review_status` as
`approved` or `rejected`. After saving the CSV, finalize it offline:

```powershell
python main.py --finalize-research-review RUN_ID
```

Finalization produces a separate approval, rejection, or incomplete decision
record, a candidate-level release report, and manifest provenance. The audit
also exports a candidate-level CSV so missing evidence, synthesis failures,
cache use, and validation outcomes remain visible across a batch. Live
synthesis reports input, output, and total token use; cache hits add no new
provider tokens. Finalization cannot approve a run whose automated gates did
not pass.

## Documentation

- PROJECT_CONTEXT.md
- VISION.md
- MANIFESTO.md
- ROADMAP.md
- ARCHITECTURE.md
- PROMPT.md
