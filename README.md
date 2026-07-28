# Discovery Engine

> Discover exceptional companies before they become widely recognized.

Discovery Engine is a modular Python platform that analyzes the North American equity universe and produces a transparent, explainable **Discovery Score** to prioritize research opportunities.

## Current Status

**Version:** v0.3 Intelligence — Sprint 2 in progress

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

## Documentation

- PROJECT_CONTEXT.md
- VISION.md
- MANIFESTO.md
- ROADMAP.md
- ARCHITECTURE.md
- PROMPT.md
