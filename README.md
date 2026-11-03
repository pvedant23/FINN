# FINN
FINN filters Indian-equity portfolio filings into a daily investor briefing.
It connects material announcements, market reactions and company financial history.
The prototype uses public data, mock holdings and no runtime model calls.

## Run
From this directory, install Python dependencies with `python -m pip install -r backend/requirements.txt` and JavaScript dependencies with `npm install`.
Offline CLI: `python -m backend.cli demo` reads committed seeds without network calls.
Offline website: `npm run build`, then `npm run preview`; after first loading, the PWA retains its last bundle offline.
Local development: `npm run dev`. This serves a dated snapshot, not a continuously live exchange feed.
Live data refresh: `python -m backend.refresh_announcements`, then `npm run build` (the refresh command currently targets the configured Sep–Nov 2026 window).
Research any Screener-supported NSE ticker: `python -m backend.cli research TICKER`, then `npm run build` to include its cached research in the frontend.
Public prototype: https://finn-investor-briefing-vedan.famedpoppy16.chatgpt.site/

## Architecture
Python fetches/cache-normalises public data and writes `data/bundle.json` under 2 MB.
React/Vite serves a static PWA; ranking, clustering, alerts and replay run in the browser.
Rules and pin/dismiss state use localStorage. There is no runtime backend or model service.

## Features
- Built: 16-holding feed, reaction inputs, tiers, clustering, replay, rules, local alerts, pin/dismiss and offline PWA.
- Built: any-ticker research CLI; 20 bundled companies, including CAMS; annual/quarterly tables and company modules.
- Partial: validated results cards for TCS, CDSL and KPRMILL only; other results are filing-link-only.
- Partial: Infosys curated transcript analysis and supplied public-source management bios, with sources and confidence labels.
- Not built: automated narrative analysis, arbitrary-ticker in-app fetching, live Ask, server backend and push delivery.

## Costs and evidence
Zero model calls in the app; model API cost is zero. Hosting and market-data service costs are not measured here.
The supplied curated content was written with Claude outside the app; this is not an automated app capability.
Research tables are via Screener, company-reported. See DECISIONS.md and docs/research-coverage.md for limits.
Validation: `npm test` is the existing browser-logic test command; `python -m unittest backend.test_finance backend.test_bundle` is the finance/pipeline suite.
