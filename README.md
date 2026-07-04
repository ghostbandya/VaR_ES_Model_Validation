# VaR/ES Model Validation & Backtesting Dashboard

A Model Risk-style validation exercise: computes Value-at-Risk three ways —
Historical Simulation, Parametric (Variance-Covariance), and Monte Carlo
(Student-t) — plus Expected Shortfall at 97.5% (the FRTB Internal Models
Approach standard), backtests each model against realized P&L (Kupiec
proportion-of-failures test, Christoffersen independence test), classifies
Basel traffic-light zones over time, runs a champion/challenger divergence
analysis between the models, and tracks rolling performance drift. Output is
a self-contained interactive HTML dashboard (Plotly) and a Word validation
report (python-docx), optionally annotated with a same-day narrative brief
written by the Anthropic API.

Built as a portfolio project to mirror the "review, challenge, validate"
and ongoing performance-monitoring responsibilities described in
market/model risk job postings — this is a full independent validation
workflow (methodology + statistics + reporting), not just a VaR calculator.

## Why this matters (FRTB / Basel context)

Regulators don't take a bank's VaR model on faith. Basel's traffic-light
backtesting framework and the FRTB IMA rules require banks to continuously
prove their internal models produce the coverage they claim:

- **Kupiec test** — does the historical exception rate match the model's
  stated confidence level?
- **Christoffersen test** — do exceptions cluster in time (a sign the model
  misses volatility regimes), rather than arriving independently as a
  well-calibrated model would predict?
- **Basel traffic-light zones** — models with too many exceptions in a
  trailing 250-day window face escalating regulatory capital multipliers
  (Green → Yellow → Red).
- **Champion/challenger analysis** — is the model actually in production
  (the "champion") diverging materially from alternative ("challenger")
  methodologies, and if so, in which direction?

This project runs all of that on a real, static multi-asset portfolio with
real daily market data, rather than synthetic examples.

## Sample portfolio

$100M notional, static weights, priced from 2014 to present (~2,900
out-of-sample trading days) via `yfinance`:

| Ticker | Asset class | Weight |
|---|---|---|
| SPY | US Large-Cap Equity | 30% |
| QQQ | US Tech Equity | 20% |
| TLT | 20+Y US Treasury | 25% |
| GLD | Gold | 15% |
| EEM | Emerging Markets Equity | 10% |

## Architecture

```
config.yaml               portfolio, model parameters, brief settings -- edit this,
                          not the source files, to point the pipeline at a different
                          portfolio or change thresholds
main.py                   orchestrator: fetch -> engine -> analysis -> brief ->
                          build_dashboard -> build_report
src/
  config.py               load_config() / tickers() / weights() helpers
  fetch_data.py           pulls daily prices via yfinance, config-driven, retries per ticker
  engine.py               rolling 250-day VaR/ES, three methods, config-driven
  stats.py                pure Kupiec / Christoffersen / Basel-zone functions (unit-tested,
                          no file I/O)
  analysis.py             runs the backtests via stats.py, computes zones, champion/
                          challenger divergence, rolling drift; writes dashboard_data.json
  brief.py                optional Anthropic API call: a same-day Model Risk narrative,
                          built from a small derived summary (not the full time series)
                          to keep token cost low; degrades gracefully with no API key
  build_dashboard.py      merges dashboard_data.json (+ brief.txt) into the HTML template
  build_report.py         builds the Word validation report (python-docx)
templates/
  dashboard_template.html Plotly dashboard shell
tests/
  test_stats.py           pytest: invariant/property tests for stats.py
output/                   gitignored; all generated artifacts land here
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # optional -- add ANTHROPIC_API_KEY to enable the daily brief
python main.py
```

Outputs land in `output/`: `prices.csv`, `backtest_results.csv`,
`dashboard_data.json`, `dashboard.html`, `report.docx`, and (if an API key is
configured) `brief.txt`.

### CLI flags

- `--skip-fetch` — reuse the existing `output/prices.csv` instead of pulling
  fresh data (useful for iterating on the analysis/reporting steps).
- `--no-brief` — skip the Anthropic API call entirely (no key required).
- `--config PATH` — use a config file other than the repo-root `config.yaml`.

## Configuration

Everything portfolio- or model-specific lives in `config.yaml`: the asset
list and weights, notional, data start date, VaR/ES confidence levels,
estimation window, Monte Carlo path count, the champion/challenger
divergence threshold, and which model is the designated champion. Nothing
under `src/` hardcodes a ticker, weight, or threshold — change the
portfolio or parameters there and rerun `main.py`.

## Methodology summary

- **Historical Simulation** — empirical quantile of the trailing window's
  realized portfolio P&L. No distributional assumption.
- **Parametric (Variance-Covariance)** — assumes jointly Normal asset
  returns; VaR/ES follow in closed form from the trailing covariance matrix.
- **Monte Carlo** — correlated draws from a multivariate Student-t
  distribution, with degrees of freedom re-estimated each window from
  realized kurtosis, to capture fat tails the Normal model misses.

All three are recomputed on a rolling 250-day window so every forecast is
fully out-of-sample, then backtested against next-day realized P&L.

## Screenshots

Not included in this checkout — the dashboard is a self-contained HTML file
(`output/dashboard.html`) with embedded data; open it directly in a browser
to view it interactively.

## Tests

```bash
pytest tests/
```

`tests/test_stats.py` covers `src/stats.py` with invariant/property checks
rather than hardcoded textbook critical values (rate-matching data doesn't
reject, degenerate 0-exception/all-exception/0-observation inputs don't
crash, and a clustered exception pattern scores measurably higher on the
independence test than a spread-out pattern with the same total count).

## Disclaimer

Educational/demo project, not investment advice. Simplified assumptions
throughout: static daily-rebalanced weights, no transaction costs or
slippage, no intraday risk, and a single static portfolio rather than a
live book. Not a substitute for a bank's actual model validation process.
