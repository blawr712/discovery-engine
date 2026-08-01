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
- Added offline recalibration from complete atomic run checkpoints
- Added decision-ready reports for every passing weighted scenario
- Added rank-movement, core-factor, peer, and data-treatment explanations
- Added combined top-25 scenario review and composition summary artifacts
- Added recalibration provenance to saved run manifests
- Added side-by-side passing-scenario comparison and consensus ranking
- Added rank sensitivity and top-10/25/50/100 agreement measurements
- Added conservative automatic scenario recommendation with gate validation
- Selected the passing 80/20 model as the configured v0.3 research scenario
- Added the final selected v0.3 research-candidate queue and decision record
- Added offline top-N research-packet generation from the selected v0.3 queue
- Added deterministic technical, fundamental, peer, quality, and question data
- Added a pluggable research-provider interface and versioned safe prompt
- Added persistent synthesis caching and per-company provider failure isolation
- Added JSON and Markdown research artifacts with manifest provenance
- Kept AI synthesis disabled by default and unable to change scores or ranks
- Added opt-in, cached primary SEC filing collection for research candidates
- Added curated source manifests with HTTPS allowlists and source priorities
- Added evidence freshness, SHA-256 hashes, deduplication, and failure isolation
- Added citation validation against attached evidence and explicit claim classes
- Added evidence provenance to research packets and saved run manifests
- Added evidence cache hit, miss, expiry, and read-error run statistics
- Added opt-in OpenAI Responses API research synthesis with strict JSON schema
- Added bounded filing excerpts and prompt-injection-resistant source handling
- Required evidence-bound citations for every sourced synthesis claim
- Added interpretation labels and rejection of ranking or recommendation fields
- Added model-aware synthesis caching, failure isolation, and no-evidence skips
- Added validated claim/citation metrics and readable research brief exports
- Added offline saved-research audits with configurable acceptance gates
- Added country evidence, synthesis, citation, section, error, and integrity metrics
- Added claim-level human-review queues with explicit accuracy/support decisions
- Added guarded research-review finalization and manifest acceptance provenance

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
