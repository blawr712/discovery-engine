# Architecture

Universe Engine
↓
Pre-Filter Engine
↓
Data Engine
↓
Scoring Engine
↓
Research Engine
↓
Reporting Engine

## Responsibilities

Universe Engine: Build and maintain investable universe.

Pre-Filter Engine: Remove companies that do not meet baseline requirements.

Data Engine: Retrieve market and metadata.

Scoring Engine: Calculate Discovery Score only.

Research Engine: Generate explainable research summaries.

Reporting Engine: Export reports and dashboards.

## Configuration

Runtime configuration belongs in:
- config/settings.json
- config/strategy.json
