"""
Backtesting statistics, Basel traffic-light zones over time, champion/
challenger divergence, and rolling performance drift. Reads
output/backtest_results.csv, writes output/dashboard_data.json.
"""
import json
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from config import load_config, OUTPUT_DIR
from stats import kupiec_test, christoffersen_test, basel_zone, basel_multiplier_addon

MODEL_NAMES = {
    "hs": "Historical Simulation",
    "param": "Parametric (Var-Cov)",
    "mc": "Monte Carlo (Student-t)",
}
CHALLENGERS = ["param", "mc"]


def sanitize(obj):
    """Recursively replace NaN/Inf floats with None so output is strict JSON."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def main(cfg: dict | None = None):
    cfg = cfg or load_config()
    m = cfg["model"]
    var_cl = float(m["var_confidence"])
    es_cl = float(m["es_confidence"])
    roll_window = int(m["estimation_window"])
    divergence_thresh = float(m["divergence_threshold"])
    champion = m["champion"]
    challengers = [k for k in MODEL_NAMES if k != champion]

    df = pd.read_csv(OUTPUT_DIR / "backtest_results.csv", parse_dates=["date"])
    n = len(df)
    df["realized_loss"] = -df["realized_pnl"]
    for k in MODEL_NAMES:
        df[f"{k}_exception"] = (df["realized_loss"] > df[f"{k}_var99"]).astype(int)

    # ---- Overall + yearly backtests ----
    overall_backtest = {}
    for k in MODEL_NAMES:
        exc = df[f"{k}_exception"].values
        overall_backtest[k] = {
            "model": MODEL_NAMES[k],
            "kupiec": kupiec_test(exc, var_cl),
            "christoffersen": christoffersen_test(exc, var_cl),
        }

    df["year"] = df["date"].dt.year
    yearly_backtest = {k: [] for k in MODEL_NAMES}
    for k in MODEL_NAMES:
        for yr, g in df.groupby("year"):
            exc = g[f"{k}_exception"].values
            kt = kupiec_test(exc, var_cl)
            yearly_backtest[k].append({
                "year": int(yr), "n_obs": kt["n_obs"], "exceptions": kt["exceptions"],
                "exception_rate": kt["exception_rate"], "kupiec_lr": kt["lr_stat"],
                "kupiec_reject_95": kt["reject_95"],
            })

    # ---- Basel traffic-light zones over time ----
    zone_series = {k: [] for k in MODEL_NAMES}
    for k in MODEL_NAMES:
        roll_count = df[f"{k}_exception"].rolling(roll_window, min_periods=roll_window).sum()
        for i in range(n):
            c = roll_count.iloc[i]
            if pd.isna(c):
                continue
            c = int(c)
            zone_series[k].append({
                "date": df["date"].iloc[i].strftime("%Y-%m-%d"),
                "breach_count_250d": c, "zone": basel_zone(c),
                "multiplier_addon": basel_multiplier_addon(c),
            })
    current_zone = {k: (zone_series[k][-1] if zone_series[k] else None) for k in MODEL_NAMES}

    # ---- Champion vs challenger ----
    champ_var = df[f"{champion}_var99"]
    challenger_stats, divergence_series = {}, {"date": df["date"].dt.strftime("%Y-%m-%d").tolist()}
    for ch in challengers:
        ch_var = df[f"{ch}_var99"]
        rel_diff = (ch_var - champ_var) / champ_var
        flagged = rel_diff.abs() > divergence_thresh
        divergence_series[f"{ch}_rel_diff"] = rel_diff.round(4).tolist()
        divergence_series[f"{ch}_flagged"] = flagged.astype(int).tolist()
        challenger_stats[ch] = {
            "model": MODEL_NAMES[ch],
            "pct_days_flagged": float(flagged.mean() * 100),
            "mean_rel_diff": float(rel_diff.mean() * 100),
            "mean_abs_rel_diff": float(rel_diff.abs().mean() * 100),
            "max_rel_diff": float(rel_diff.max() * 100),
            "min_rel_diff": float(rel_diff.min() * 100),
            "correlation_with_champion": float(np.corrcoef(ch_var, champ_var)[0, 1]),
        }

    # ---- Rolling performance drift ----
    z_var = scipy_stats.norm.ppf(var_cl)
    drift_series = {"date": df["date"].dt.strftime("%Y-%m-%d").tolist()}
    for k in MODEL_NAMES:
        roll_rate = df[f"{k}_exception"].rolling(roll_window, min_periods=60).mean() * 100
        drift_series[f"{k}_rolling_breach_rate_pct"] = roll_rate.round(3).tolist()
        var_implied_vol = df[f"{k}_var99"] / z_var
        realized_vol_60d = df["realized_pnl"].rolling(60, min_periods=20).std()
        drift_series[f"{k}_calibration_ratio"] = (realized_vol_60d / var_implied_vol).round(4).tolist()
    drift_series["expected_breach_rate_pct"] = (1 - var_cl) * 100

    timeseries = {
        "date": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "realized_pnl": df["realized_pnl"].round(0).tolist(),
        **{f"{k}_var99": df[f"{k}_var99"].round(0).tolist() for k in MODEL_NAMES},
        **{f"{k}_es975": df[f"{k}_es975"].round(0).tolist() for k in MODEL_NAMES},
        **{f"{k}_exception": df[f"{k}_exception"].tolist() for k in MODEL_NAMES},
        "mc_df": df["mc_df"].round(2).tolist(),
    }

    summary = {
        "n_obs": n,
        "start_date": df["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "notional": cfg["portfolio"]["notional"],
        "portfolio": cfg["portfolio"]["assets"],
        "var_confidence": var_cl, "es_confidence": es_cl, "estimation_window": roll_window,
        "mean_realized_pnl": float(df["realized_pnl"].mean()),
        "std_realized_pnl": float(df["realized_pnl"].std()),
        "worst_day_pnl": float(df["realized_pnl"].min()),
        "worst_day_date": df.loc[df["realized_pnl"].idxmin(), "date"].strftime("%Y-%m-%d"),
        "best_day_pnl": float(df["realized_pnl"].max()),
        "best_day_date": df.loc[df["realized_pnl"].idxmax(), "date"].strftime("%Y-%m-%d"),
    }

    output = sanitize({
        "summary": summary, "timeseries": timeseries,
        "overall_backtest": overall_backtest, "yearly_backtest": yearly_backtest,
        "zone_series": zone_series, "current_zone": current_zone,
        "champion": champion, "challenger_stats": challenger_stats,
        "divergence_series": divergence_series, "drift_series": drift_series,
        "models": MODEL_NAMES,
    })

    out_path = OUTPUT_DIR / "dashboard_data.json"
    with open(out_path, "w") as f:
        json.dump(output, f)
    print(f"Saved {out_path.name}")
    return output


if __name__ == "__main__":
    main()
