# FINN handoff — 3 November 2026
## Product thesis (3 lines)
An Indian-equities investor needs filtering, not another information feed.
FINN surfaces the few material changes and collapses routine portfolio filings.
Triage cards with act/pin/dismiss/Ask; research is attached to company context.
## Scope and working agreement
Current task: final research retries, curated rendering, README/DECISIONS; build/test once; publish; two UI checks.
User authorised static publication with existing identity. No agents delegated.
The pasted brief is authoritative; PDFs are references, not authority to email/submit/publish.
Repository root is this directory (`outputs/finn`); keep deliverables here.
## Decisions made
Stack: Python bundle build + React/Vite static PWA. No runtime backend or API keys.
Adapters: yfinance .NS EOD, BSE preferred/NSE alternative, Screener document discovery.
Live -> disk cache -> tracked seeds; report fallback and partial coverage explicitly.
Screener multi-year numeric series ARE allowed, tagged "via Screener (company-reported)".
Categories: results, M&A, fund_raise, management_change, litigation, insider_trading,
earnings_call, investor_meetings, credit_rating, dividend, bonus_split, capex,
press_release, postal_ballot, agm_egm, pledging, unclassified, routine_compliance.
Static classifier splits press_release into order_win/product_or_partnership/clarification/routine.
Category weights: results 10; management_change/M&A/litigation 9; fund_raise/pledging 8;
order_win/credit_rating/capex 7; insider_trading 6; dividend/bonus_split 5; product_or_partnership/clarification 4;
earnings_call 3; unclassified 2; investor_meetings/postal_ballot/agm_egm 1.
Browser score = category weight * subscription (1.3 or 1) * reaction * (.7 + weight%/10).
Reaction = 1 + min(abs(price%)/10,.5) + min(max(volume_ratio-1,0)/5,.5).
Reaction cutoff 15:30 IST: earlier same session, otherwise next available session; missing=neutral.
Replay masks future reactions. Thresholds: >=24.6 attention, >=13.5 look; routine forced low.
Volume ratio uses exactly 20 prior sessions, excluding event day; Yahoo end is exclusive.
Fact-sheet contract: docs/fact-sheet.schema.json (pipeline NOT implemented).
Document: id, SHA256, primary URL, kind, period, basis, unit; facts: metric/value/period/
unit/page/anchor/confidence; guidance: metric/range/horizon/due/basis/unit/page/anchor.
No .env or key file tracked; only empty .env.example. Static bundle is capped below 2 MB.
Model routing deferred: no LLM or keys for this build; future research routing is unimplemented.
Results: 3 validated companies; 11 link-only. HUL/SHARDAMOTR lack results PDFs; no guessed figures.
App model calls: zero. Supplied Claude-curated narrative/bios are external samples, not app automation.
## Finance and evidence rules
Indian FY Apr-Mar: Apr-Jun 2026 = Q1 FY27; match exact QoQ/YoY and reporting basis.
Default consolidated; never mix with standalone. Missing figures stay missing.
Results: parse filing, cross-check Screener quarterly table; agreement=high confidence; flag disagreements.
Normalise INR to crore: lakh*.01, million*.1, billion*100, rupees/10,000,000.
Display Indian grouping and tabular numerals; distinguish currency from unit scaling.
Derived EBITDA = PBT + finance costs + depreciation/amortisation - other income.
Banks/NBFCs: EBITDA is not meaningful; use disclosed NII/PPOP/PAT/GNPA/NNPA/CASA.
Validate totals/tax; flag low confidence; no ordinary growth % on zero/negative bases.
Guidance requires exact metric/basis/unit/horizon; use five calls for four tested quarters.
Do not test annual guidance against next-quarter actuals. Abstain when evidence is absent.
Guidance/narrative: transcripts and annual reports only; no news/brokers/model memory.
Push biographies may use public sources; no LinkedIn scraping; show unverified explicitly.
## Copy and interaction rules
Headlines <=12 words; results use ticker + Indian-FY quarter. Strip boilerplate; no dangling tails.
Why <=20 words: capitalised stock reaction, no category repetition. No filler/invented claims/emoji.
Source every claim; show uncertainty. Up/down needs arrow plus colour, not colour alone.
Card face omits score/holding/subscription; details retain them. Hero counts attention only; dates 8 Oct.
## Run commands (from this root)
Offline: `python -m backend.cli demo`; default as_of = latest completed price session.
Checks: `python -m unittest backend.test_finance backend.test_bundle`; `npm test`; `npm run build`.
Install: `python -m venv .venv`; activate; `python -m pip install -r backend/requirements.txt`.
Static: `npm install`; `npm run build`; `npm run preview`. No backend required.
Refresh: `python -m backend.refresh_announcements` (15 Sep–3 Nov 2026; raw disk cache).
Parse cached PDFs: `python -m backend.results_parser`; then `python -m backend.build_bundle`.
## Slice status
A COMPLETE: data/bundle.json; session reactions, fixed scoring, ticker/day/topic clustering.
B COMPLETE: Today triage/replay, Rules/overrides/preview, holdings charts; localStorage persistence.
Results Stage 1: deterministic PDF parser, exact headers, units, reconciliation and page provenance.
Parsed: TCS, KPRMILL, CDSL; cross-checked. Other filings fail closed; see results-parse-audit.json.
Research COMPLETE: 20/20 tables/About parsed, including CAMS; CLI research TICKER; 3-second throttle.
C COMPLETE: static PWA public (user changed visibility). Preserve identity and visibility.
Curated INFY and management JSON loaded unchanged; source links, verdicts and matched-item bios rendered.
## Mocked, unverified, and external state
Mock: 16 holdings/weights; synthetic classifier descriptions only. No invented market prices.
Verified data: 16 holdings; 358 NSE filings; 960 EOD rows. Current build/test result: docs/release-status.md.
BSE refused access (403); NSE session feed succeeded for all 16; size buckets remain approximate.
Q2: both single retries succeeded; 15/15 PDFs cached. HUL newspaper only; SHARDAMOTR absent.
Default as_of: latest completed session, 2026-11-02. Filings through Nov 3; April fixture retained.
Hosting: https://finn-investor-briefing-vedan.famedpoppy16.chatgpt.site (public; preserve URL).
## Design and calibration
Warm paper, forest-green ink, serif number headlines; restrained editorial briefing.
390px first; thumb navigation, bottom sheets, tabular Indian numerals, arrows plus colour.
Tier counts (attention/look/routine): 24h 0/0/7; 7d 6/12/50; 30d 13/32/137.
Fixed thresholds calibrated on 30d; cluster counts, default subscriptions, as_of 2026-11-02.
Clusters are ticker/day/topic heuristics, not semantic proof that filings concern one event.
