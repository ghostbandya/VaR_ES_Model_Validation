# VaR/ES Model Validation & Backtesting Dashboard — Handoff Notes

Context for picking this project up in Claude Code. Written mid-rework, so it
covers what exists, what's mid-flight, and what's left.

## What this project is

A Model Risk-style tool: computes VaR three ways (Historical Simulation,
Parametric Variance-Covariance, Monte Carlo/Student-t) plus Expected
Shortfall at 97.5% (FRTB IMA) for a sample multi-asset portfolio, backtests
each model against realized P&L (Kupiec POF test, Christoffersen
independence test), classifies Basel traffic-light zones over time, runs a
champion/challenger divergence analysis, and tracks rolling performance
drift. Built as interview prep for model-risk-adjacent roles (Marex/
Schroders JDs mentioned "review, challenge, validate" and performance
monitoring — this project mirrors that).

Sample portfolio: SPY 30% / QQQ 20% / TLT 25% / GLD 15% / EEM 10%, $100M
notional, real daily prices via yfinance from 2014 to present (~2,900
out-of-sample trading days).

## History: how we got here

1. **First built inside Cowork** (Claude's desktop tool) as a working
   prototype: `engine.py` (VaR/ES math) → `analysis.py` (backtests, zones,
   drift) → a self-contained HTML dashboard (Plotly) + a Word report
   (built with the Node.js `docx` package via a `generate_report.js`
   script). This produced two real deliverables and they're correct —
   the math and statistical logic are validated (see "Known-good results"
   below).
2. Added a "daily LLM brief" feature: originally via a Cowork **scheduled
   task** that re-ran the pipeline daily and had Claude write a short
   Model-Risk-analyst narrative each time, injected into both the
   dashboard and report as a highlighted callout box.
3. **User decided to make this a standalone GitHub project** instead of a
   Cowork-only tool. That triggered the rework this file describes:
   - Retired the Cowork scheduled task (disabled, not deleted).
   - Converting the Node.js/docx report builder to pure Python
     (`python-docx`) so the whole repo is `pip install -r
     requirements.txt && python main.py` with no Node dependency.
   - Moving from hardcoded portfolio/model parameters to a `config.yaml`.
   - Moving the "daily brief" from a Cowork scheduled task to a direct
     Anthropic API call inside the pipeline itself (`src/brief.py`), so
     running `main.py` produces a fresh Claude-written brief using the
     user's own `ANTHROPIC_API_KEY`.
   - Restructuring into a clean `src/` + `output/` + `templates/` +
     `tests/` layout suitable for a portfolio piece on GitHub.

## Decisions already made (don't re-litigate these)

- **Report builder: python-docx, not Node.js.** User explicitly chose this
  for a single-language, easy-clone repo. Formatting is intentionally
  simpler than the original JS version (no custom fonts beyond Calibri, no
  TOC hyperlinks) but should stay professional — tables with navy headers,
  colored PASS/FAIL and zone cells, a highlighted callout box for the daily
  brief.
- **Cowork scheduled task: retired.** User will run `main.py` themselves
  (manually or via their own cron / Windows Task Scheduler) once this is on
  GitHub. Don't re-add Cowork-specific automation.
- **Daily brief: real Anthropic API call, not a Cowork-side LLM step.**
  Needs `ANTHROPIC_API_KEY` via `.env` (python-dotenv). Must degrade
  gracefully (skip with a clear message, don't crash) if no key is set —
  this was tested and works.
- **Portfolio/model params live in `config.yaml`**, not hardcoded. Nothing
  under `src/` should have a hardcoded ticker, weight, or threshold.
- **Brief context sent to the API should be compact**, not the full
  ~1.3MB `dashboard_data.json` — send a small derived summary (current
  zone, latest exceptions, headline backtest stats, last ~20 days of
  drift) to keep cost/tokens low. Already implemented this way in
  `src/brief.py`.

## Target directory structure

```
var-es-model-validation/          <- repo root (this is where PROJECT_HANDOFF.md lives)
├── README.md                     <- NOT YET WRITTEN
├── requirements.txt              <- NOT YET WRITTEN
├── .env.example                  <- NOT YET WRITTEN
├── .gitignore                    <- NOT YET WRITTEN
├── config.yaml                   <- DONE
├── src/
│   ├── config.py                 <- DONE (load_config, tickers(), weights() helpers)
│   ├── stats.py                  <- DONE (pure kupiec_test/christoffersen_test/basel_zone functions,
│   │                                 no file I/O, written specifically to be unit-testable)
│   ├── fetch_data.py              <- DONE (yfinance pull, config-driven, retries per ticker)
│   ├── engine.py                  <- DONE (rolling 250-day VaR/ES x3 methods, config-driven)
│   ├── analysis.py                <- DONE (Kupiec/Christoffersen via stats.py, Basel zones,
│   │                                 champion/challenger, drift, writes dashboard_data.json)
│   ├── brief.py                   <- DONE (Anthropic API call, compact context builder,
│   │                                 graceful no-key fallback -- tested, works)
│   ├── build_dashboard.py         <- DONE (merges dashboard_data.json + brief.txt into
│   │                                 templates/dashboard_template.html -> output/dashboard.html;
│   │                                 exposes load_merged_data() reused by build_report.py)
│   └── build_report.py            <- DONE, JUST FIXED (see "Known gotcha" below) -- python-docx
│                                      version of the report, includes the daily-brief callout box
├── templates/
│   └── dashboard_template.html    <- DONE (copied from the earlier Cowork build, already has
│                                      the narrative-brief panel wired in via DATA.narrative_brief)
├── main.py                        <- NOT YET WRITTEN (the actual ask that started this rework:
│                                      orchestrate fetch -> engine -> analysis -> brief ->
│                                      build_dashboard -> build_report, with argparse flags
│                                      --skip-fetch, --no-brief, --config, and a printed
│                                      terminal summary at the end)
├── tests/
│   └── test_stats.py              <- NOT YET WRITTEN (unit tests for src/stats.py: rate-matching
│                                      sanity checks, 0/all-exception edge cases, and a
│                                      clustered-vs-spread comparative test proving
│                                      christoffersen_test actually detects clustering)
└── output/                        <- gitignored; dashboard_data.json, prices.csv,
                                       backtest_results.csv, dashboard.html, report.docx,
                                       brief.txt all land here. Currently has real generated
                                       output from manual testing (safe to keep or wipe).
```

## Known-good results (already validated, don't recompute from scratch to "check" — trust these)

Full backtest, 2014-12-31 to 2026-07-02, 2,892 out-of-sample days, 99% VaR / 97.5% ES:

- **Historical Simulation**: 33 exceptions (1.14% rate) — passes Kupiec (p=0.456), fails
  Christoffersen independence (p<0.001, exceptions cluster in stress periods).
- **Parametric**: 69 exceptions (2.39% rate) — fails both Kupiec and Christoffersen. Worst
  years: 2018 (13 exceptions) and 2022 (16 exceptions), both regimes where equities and
  bonds sold off together — the Normal-distribution assumption badly understates this.
- **Monte Carlo (Student-t)**: 55 exceptions (1.90% rate) — fails both, but less badly
  than Parametric (fat-tail correction helps partially).
- Current (as of 2026-07-02): HS is Basel Green (1 exception/250d), Parametric and MC are
  both Yellow (7 and 6 exceptions/250d respectively).
- Champion (HS) vs challengers: Parametric diverges >20% from HS on 45% of days (mean
  -19.6%, i.e. systematically lower/more permissive). MC diverges on 30% of days, tracks
  HS more closely (corr 0.905 vs 0.885 for Parametric).

These numbers came from real yfinance data and were sanity-checked (e.g. worst single day
was 2020-03-12, the real COVID crash date — confirms the pipeline is pulling and computing
correctly). If a rebuild produces very different headline numbers, something broke.

## Known gotcha: file writes to this mounted drive can silently truncate

While building `build_report.py`, several large file writes (via Claude's Edit tool, a
bash heredoc, and even a plain Python `open().write()`) silently truncated mid-file when
writing directly to a path under `D:\VaR_ES validation\...` from within the Cowork
sandbox. Symptom: file looks fine by line count at first glance but cuts off mid-statement,
or an unrelated stale-bytecode-cache-like symptom appears (Python running old logic after a
source edit). This was specific to Cowork's sandboxed bridge to the mounted Windows drive —
**it's unlikely to affect Claude Code running natively on the machine**, but if you see a
script behaving like it's running old code, or a file that looks truncated mid-line/mid-word,
diff it against what you expect before assuming the logic is wrong.

Workaround used successfully: write to a local scratch path first, verify (syntax check,
`wc -l`, tail content), then copy into the final destination and diff to confirm the copy is
byte-identical.

**Leftover artifact to delete:** `src/build_report_v2.py` — a debug scratch copy created
while diagnosing the above. It's broken/incomplete (truncated mid-file) and unused. Delete it.
Also worth checking `src/__pycache__/` for stale `.pyc` files if anything behaves oddly after
edits — remove that directory.

## Also still lying around (from the pre-rework Cowork version, now superseded)

`D:\VaR_ES validation\pipeline\`, `D:\VaR_ES validation\archive\`, and root-level
`VaR_ES_Model_Validation_Dashboard.html` / `.docx` are the **old** Cowork-oriented build
(Node.js-based report generation, no config.yaml, archive-by-date design). They still work
but are superseded by `var-es-model-validation/`. Safe to delete once the new structure is
confirmed working, or keep as a reference — your call.

## Remaining work (in suggested order)

1. **`main.py`** — orchestrator at repo root. Add `src/` to `sys.path`, import the six
   modules, run in order: `fetch_data.main()` (skip if `--skip-fetch`), `engine.main()`,
   `analysis.main()`, `brief.main()` (skip if `--no-brief`), `build_dashboard.main()`,
   `build_report.main()`. Argparse flags: `--skip-fetch`, `--no-brief`, `--config PATH`.
   End with a printed terminal summary: current zone + exception count per model, whether a
   brief was generated. Pass the loaded `cfg` dict through to each module's `main(cfg)` so
   config is only loaded once.
2. **`tests/test_stats.py`** — pytest, import from `src/stats.py` (may need a
   `sys.path.insert` or a `conftest.py` / `pyproject.toml` to make `src` importable from
   `tests/). Cover: exception rate exactly matching expected → low LR/no reject; very high
   rate → reject; 0 exceptions and all-exceptions edge cases don't crash; a comparative test
   showing `christoffersen_test` gives a higher `lr_ind` for a clustered exception pattern
   than a spread-out one with the same total count (don't hardcode "textbook" critical
   values you haven't independently verified — test properties/invariants instead, which is
   what was done for the earlier Cowork-side testing too).
3. **`requirements.txt`**: pandas, numpy, scipy, yfinance, python-docx, python-dotenv,
   PyYAML, anthropic. Pin reasonable minimum versions.
4. **`.env.example`**: `ANTHROPIC_API_KEY=sk-ant-...` with a comment that it's optional
   (pipeline works without it, just skips the brief).
5. **`.gitignore`**: `output/`, `__pycache__/`, `*.pyc`, `.env`, `.venv/`, `venv/`,
   `.DS_Store`.
6. **`README.md`**: motivation/FRTB context, architecture summary, setup (`pip install -r
   requirements.txt`, copy `.env.example` to `.env`, `python main.py`), config.yaml
   explanation, methodology summary, a couple of screenshots once the dashboard is
   confirmed working, and a disclaimer (educational/demo project, not investment advice,
   simplified assumptions — static daily-rebalanced weights, no transaction costs).
7. **End-to-end test**: run `python main.py --no-brief` (no API key needed) from repo root,
   confirm `output/dashboard.html` and `output/report.docx` both generate correctly and
   match the known-good numbers above. Then run `pytest tests/`. If an `ANTHROPIC_API_KEY`
   is available, also test a full run with the brief enabled and check the callout box
   renders in both the dashboard and the docx.

## Verification approach used so far (worth continuing)

- Python syntax check every new file (`python3 -c "import ast; ast.parse(...)"`) before
  running it.
- `python-docx` output validated via LibreOffice conversion to PDF + visual page-by-page
  review (`soffice --headless --convert-to pdf`, then `pdftoppm -jpeg`), not just "did it
  save without an exception."
- The Word doc's `word/settings.xml` had a minor schema nag (`w:zoom` missing
  `w:percent` — a known harmless python-docx quirk); fixed via a small oxml patch
  (`fix_zoom_setting` in `build_report.py`). Worth re-checking with a real validator once
  the rest of the doc is finalized, though it's cosmetic and Word/LibreOffice both open the
  file fine either way.
