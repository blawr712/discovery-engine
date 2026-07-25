# Changelog

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
