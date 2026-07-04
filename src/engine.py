"""
VaR/ES computation engine: Historical Simulation, Parametric (Variance-
Covariance), and Monte Carlo (Student-t), plus Expected Shortfall, on a
rolling estimation window. All parameters come from config.yaml.
"""
import numpy as np
import pandas as pd
from scipy import stats

from config import load_config, weights, OUTPUT_DIR

np.random.seed(42)


def main(cfg: dict | None = None):
    cfg = cfg or load_config()
    m = cfg["model"]
    w = weights(cfg)
    notional = float(cfg["portfolio"]["notional"])
    window = int(m["estimation_window"])
    var_cl = float(m["var_confidence"])
    es_cl = float(m["es_confidence"])
    n_mc = int(m["mc_paths"])

    prices = pd.read_csv(OUTPUT_DIR / "prices.csv", index_col=0, parse_dates=True)
    tick_cols = [a["ticker"] for a in cfg["portfolio"]["assets"]]
    log_ret = np.log(prices[tick_cols] / prices[tick_cols].shift(1)).dropna()
    port_pnl_full = (log_ret.values @ w) * notional
    dates = log_ret.index
    ret_matrix = log_ret.values
    n = len(log_ret)

    results = {
        "date": [], "realized_pnl": [],
        "hs_var99": [], "hs_es975": [],
        "param_var99": [], "param_es975": [],
        "mc_var99": [], "mc_es975": [], "mc_df": [],
    }

    for t in range(window, n):
        win_returns = ret_matrix[t - window:t, :]
        win_port_ret = win_returns @ w
        win_port_pnl = win_port_ret * notional

        # Historical Simulation
        sorted_pnl = np.sort(win_port_pnl)
        hs_var_idx = int(np.floor((1 - var_cl) * window))
        hs_var99 = -sorted_pnl[hs_var_idx]
        es_idx = max(int(np.ceil((1 - es_cl) * window)), 1)
        hs_es975 = -sorted_pnl[:es_idx].mean()

        # Parametric (Normal)
        mu = win_returns.mean(axis=0)
        cov = np.cov(win_returns, rowvar=False)
        port_mu = mu @ w
        port_sigma = np.sqrt(max(w @ cov @ w, 1e-16))
        z_var = stats.norm.ppf(var_cl)
        param_var99 = -(port_mu - z_var * port_sigma) * notional
        z_es = stats.norm.ppf(es_cl)
        es_factor = stats.norm.pdf(z_es) / (1 - es_cl)
        param_es975 = -(port_mu - es_factor * port_sigma) * notional

        # Monte Carlo (multivariate Student-t, fat tails re-fit each window)
        kurt = stats.kurtosis(win_port_ret, fisher=False)
        df_t = 4 + 6 / (kurt - 3) if kurt > 3.05 else 30.0
        df_t = float(np.clip(df_t, 3.5, 30.0))
        try:
            L = np.linalg.cholesky(cov)
        except np.linalg.LinAlgError:
            L = np.linalg.cholesky(cov + np.eye(len(w)) * 1e-10)

        g = np.random.chisquare(df_t, size=n_mc) / df_t
        z = np.random.standard_normal(size=(n_mc, len(w)))
        corr_normal = z @ L.T
        t_scale = np.sqrt(df_t / (df_t - 2)) if df_t > 2 else 1.0
        sim_asset_ret = mu + (corr_normal / np.sqrt(g)[:, None]) / t_scale
        sim_port_pnl = (sim_asset_ret @ w) * notional

        sorted_sim = np.sort(sim_port_pnl)
        mc_var_idx = int(np.floor((1 - var_cl) * n_mc))
        mc_var99 = -sorted_sim[mc_var_idx]
        mc_es_idx = max(int(np.ceil((1 - es_cl) * n_mc)), 1)
        mc_es975 = -sorted_sim[:mc_es_idx].mean()

        results["date"].append(dates[t].strftime("%Y-%m-%d"))
        results["realized_pnl"].append(float(port_pnl_full[t]))
        results["hs_var99"].append(float(hs_var99))
        results["hs_es975"].append(float(hs_es975))
        results["param_var99"].append(float(param_var99))
        results["param_es975"].append(float(param_es975))
        results["mc_var99"].append(float(mc_var99))
        results["mc_es975"].append(float(mc_es975))
        results["mc_df"].append(float(df_t))

    df = pd.DataFrame(results)
    df["date"] = pd.to_datetime(df["date"])
    out_path = OUTPUT_DIR / "backtest_results.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path.name}: {df.shape[0]} out-of-sample days")
    return df


if __name__ == "__main__":
    main()
