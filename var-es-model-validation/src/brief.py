"""
Calls the Anthropic API to write a short Model Risk narrative brief from
the day's computed results. Degrades gracefully (returns None) if no API
key is configured -- the rest of the pipeline works fine without a brief.
"""
import json
import os

from config import load_config, OUTPUT_DIR

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


SYSTEM_PROMPT = """You are a Model Risk analyst writing a short daily brief on a \
VaR/ES model validation exercise for a market risk desk. You are given the \
latest computed results (not raw data) for three VaR models -- Historical \
Simulation, Parametric (Variance-Covariance), and Monte Carlo (Student-t) -- \
backtested on a multi-asset portfolio. Write 150-250 words of plain prose \
(no markdown headers, no bullet points) covering, in order: (1) today's \
realized P&L and whether any model recorded a VaR exception, (2) each \
model's current Basel traffic-light zone and how close it is to the next \
threshold, (3) any notable champion/challenger divergence worth flagging, \
(4) any drift signal in the rolling breach rate or calibration ratio worth \
flagging, and (5) a one-line recommended action (escalate / continue \
monitoring / no action needed). Be specific with numbers. Do not restate \
the methodology -- assume the reader already knows it."""


def _build_context(data: dict, lookback_days: int) -> dict:
    """Compact, cheap-to-send summary -- not the full multi-year time series."""
    ts = data["timeseries"]
    idx = len(ts["date"])
    recent = slice(max(0, idx - lookback_days), idx)

    drift = data["drift_series"]
    recent_drift = {
        k: v[recent] if isinstance(v, list) else v
        for k, v in drift.items()
    }

    return {
        "as_of_date": data["summary"]["end_date"],
        "latest_realized_pnl": ts["realized_pnl"][-1],
        "latest_exceptions": {
            k: bool(ts[f"{k}_exception"][-1]) for k in data["models"]
        },
        "current_zone": data["current_zone"],
        "overall_backtest_headline": {
            k: {
                "exceptions": v["kupiec"]["exceptions"],
                "n_obs": v["kupiec"]["n_obs"],
                "kupiec_reject_95": v["kupiec"]["reject_95"],
                "christoffersen_reject_95": v["christoffersen"]["reject_ind_95"],
            }
            for k, v in data["overall_backtest"].items()
        },
        "champion": data["champion"],
        "challenger_stats": data["challenger_stats"],
        "recent_drift": recent_drift,
        "models": data["models"],
    }


def main(cfg: dict | None = None) -> str | None:
    cfg = cfg or load_config()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("No ANTHROPIC_API_KEY found (checked environment and .env) -- "
              "skipping the narrative brief. Set ANTHROPIC_API_KEY to enable it.")
        return None

    with open(OUTPUT_DIR / "dashboard_data.json") as f:
        data = json.load(f)

    context = _build_context(data, cfg["brief"].get("drift_lookback_days", 20))

    try:
        import anthropic
    except ImportError:
        print("The 'anthropic' package isn't installed -- run: pip install anthropic")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=cfg["brief"].get("model", "claude-haiku-4-5-20251001"),
        max_tokens=cfg["brief"].get("max_tokens", 600),
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Here is today's computed model validation data as JSON:\n\n{json.dumps(context, indent=2)}",
        }],
    )
    brief_text = "".join(block.text for block in response.content if block.type == "text").strip()

    out_path = OUTPUT_DIR / "brief.txt"
    out_path.write_text(brief_text)
    print(f"Saved {out_path.name} ({len(brief_text.split())} words)")
    return brief_text


if __name__ == "__main__":
    main()
