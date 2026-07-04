"""
Fetch latest daily prices for the configured portfolio.
Always pulls from config.data.start_date through today, so every run is
naturally up to date.
"""
import time
import pandas as pd
import yfinance as yf

from config import load_config, tickers, OUTPUT_DIR


def fetch_one(ticker, start, attempts=4, pause=2):
    for i in range(attempts):
        try:
            s = yf.download(ticker, start=start, progress=False, auto_adjust=True)["Close"]
            return s[ticker] if hasattr(s, "columns") else s
        except Exception as e:
            print(f"  retry {ticker} ({i+1}/{attempts}): {e}")
            time.sleep(pause)
    raise RuntimeError(f"Failed to fetch {ticker} after {attempts} attempts")


def main(cfg: dict | None = None):
    cfg = cfg or load_config()
    ticks = tickers(cfg)
    start = cfg["data"]["start_date"]

    print(f"Fetching {len(ticks)} tickers from {start}: {', '.join(ticks)}")
    frames = {t: fetch_one(t, start) for t in ticks}
    df = pd.DataFrame(frames).dropna()

    out_path = OUTPUT_DIR / "prices.csv"
    df.to_csv(out_path)
    print(f"Saved {out_path.name}: {df.shape[0]} rows, {df.index[0].date()} to {df.index[-1].date()}")
    return df


if __name__ == "__main__":
    main()
