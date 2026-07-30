# Changelog

## v0.3 Intelligence (in progress)

- Added the v0.3 specification and staged acceptance criteria
- Added configuration-driven structural asset classification
- Exclude obvious acquisition vehicles, shell companies, and non-equities
- Added explainable factor results, score confidence, and JSON breakdowns
- Preserved v0.2 numerical scoring during the framework transition
- Added versioned metadata caching for expanded provider fields
- Added shadow growth, profitability, cash-flow, and balance-sheet factors
- Added fundamental score, normalized score, confidence, and JSON breakdown
- Added curated top-candidate reports with separate fundamental ranking
- Added factor coverage, confidence, exclusion, country, and sector analytics
- Added deterministic interleaved Canadian/U.S. validation sampling
- Added shadow earnings-yield, sales-yield, and EV/EBITDA valuation factors
- Added shadow liquidity, leverage, and earnings-quality risk factors
- Added formal fresh, undated, missing, invalid, and stale data policies
- Added quality-adjusted fundamental confidence and report provenance
- Added officially ordered calibration CSV and aggregate analysis JSON
- Added country, sector, technical, and fundamental candidate percentiles
- Added rank correlation, top-list overlap, disagreement, and outlier analysis
- Added configurable 100/0, 80/20, and 70/30 experimental blend scenarios
- Added configurable cap/invalid policies for extreme fundamental inputs
- Added sector applicability exclusions without artificial confidence loss
- Added confidence-adjusted blends with minimum-confidence eligibility
- Added sector-relative fundamental percentiles and ineligibility explanations
- Added top-20/50/100 overlap, scenario movement, and factor-readiness analysis
- Added dynamically selected cross-market core fundamental factors
- Added country and sufficiently sized country/sector peer percentiles
- Added continuous confidence scaling toward a neutral fundamental percentile
- Constrained fundamental reranking to a top-100 pool and 25-company bands
- Added country-fairness, retention, and movement acceptance gates
- Added automatic experimental-scenario pass/fail recommendations

## v0.2.0 Performance — 2026-07-25

Validated against the complete 6,424-company North American universe:

- 3,158 companies scored successfully
- 2,964 companies removed by explainable pre-filters
- 302 companies rejected for insufficient price history
- Zero provider or pipeline errors

- Added a configuration-driven market-cap pre-filter
- Skip price-history downloads for companies rejected by the pre-filter
- Report filtered companies separately from provider errors
- Corrected nested output-directory configuration loading
- Added persistent metadata and price-history caching with configurable TTLs
- Added per-run cache statistics and recovery from unreadable cache entries
- Added bounded concurrent metadata and price-history collection
- Added deterministic result ordering, benchmark reuse, and failure isolation
- Added configurable transient-provider retries with exponential backoff
- Added retry and exhausted-attempt statistics to run summaries
- Added resumable runs with configuration and universe fingerprints
- Added atomic per-company checkpoints and structured run manifests
- Added reproducible `--tickers` and `--limit` smoke-run options
- Added shared provider pacing and global Yahoo rate-limit cooldowns
- Added separate metadata and price-history worker limits
- Made completed runs with provider errors resumable
- Added a provider circuit breaker for persistent rate limiting
- Split scoring failures from provider errors in run summaries
- Completed the v0.2 Performance milestone

## v0.1 Foundation

- Project architecture established
- JSON configuration
- US universe builder
- Canadian universe builder
- Dynamic universe loading
- Documentation v1
