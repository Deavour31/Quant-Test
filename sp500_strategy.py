"""S&P 500 두 가지 매수 전략 비교: 매일 매수 vs 하락 시 집중 매수"""

import subprocess
import sys

for _pkg in ["yfinance", "pandas", "matplotlib"]:
    try:
        __import__(_pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg, "-q"])

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

START_DATE = "2025-04-27"
END_DATE = "2026-04-27"
DAILY_KRW = 5_000
FALLBACK_FX = 1_370.0  # KRW per 1 USD


def fetch_sp500(start: str, end: str) -> pd.Series:
    df = yf.download("^GSPC", start=start, end=end, auto_adjust=True, progress=False)
    return df["Close"].squeeze()


def fetch_fx(start: str, end: str) -> tuple[pd.Series | None, str]:
    for ticker in ("KRW=X", "KRWUSD=X"):
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            if df is not None and not df.empty:
                s = df["Close"].squeeze()
                if not s.empty and s.notna().any():
                    return s, ticker
        except Exception:
            continue
    return None, "fallback"


def normalize_fx(raw: pd.Series) -> pd.Series:
    """Return series in KRW-per-USD regardless of raw ticker direction."""
    median = raw.dropna().median()
    if median < 1:  # KRW=X is quoted as USD/KRW (~0.00073), invert it
        return 1.0 / raw
    return raw


def build_data() -> tuple[pd.DataFrame, str]:
    sp500 = fetch_sp500(START_DATE, END_DATE).dropna()

    fx_raw, fx_source = fetch_fx(START_DATE, END_DATE)
    if fx_raw is None:
        fx = pd.Series(FALLBACK_FX, index=sp500.index)
    else:
        fx_norm = normalize_fx(fx_raw)
        fx = fx_norm.reindex(sp500.index).ffill().fillna(FALLBACK_FX)

    data = pd.DataFrame({"close": sp500, "fx": fx}).dropna(subset=["close"])
    data["fx"] = data["fx"].ffill().fillna(FALLBACK_FX)
    return data, fx_source


def simulate(data: pd.DataFrame) -> pd.DataFrame:
    closes = data["close"].values
    fxs = data["fx"].values
    n = len(closes)

    strat1 = [0.0] * n
    strat2 = [0.0] * n
    total_invested = [0.0] * n

    # Strategy 1: buy every day
    shares1 = 0.0
    for i in range(n):
        usd = DAILY_KRW / fxs[i]
        shares1 += usd / closes[i]
        strat1[i] = shares1 * closes[i] * fxs[i]
        total_invested[i] = DAILY_KRW * (i + 1)

    # Strategy 2: accumulate on up days, buy all on down/flat days
    shares2 = 0.0
    cash = 0.0
    for i in range(n):
        cash += DAILY_KRW
        is_down = (i == 0) or (closes[i] <= closes[i - 1])
        if is_down:
            usd = cash / fxs[i]
            shares2 += usd / closes[i]
            cash = 0.0
        strat2[i] = shares2 * closes[i] * fxs[i] + cash

    data = data.copy()
    data["strat1"] = strat1
    data["strat2"] = strat2
    data["total_invested"] = total_invested
    return data


def plot_results(data: pd.DataFrame, fx_source: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))

    ax.plot(data.index, data["strat1"],
            label="Strategy 1: Daily Buy", color="steelblue", linewidth=2)
    ax.plot(data.index, data["strat2"],
            label="Strategy 2: Dip Buy (buy all on down days)", color="tomato", linewidth=2)
    ax.plot(data.index, data["total_invested"],
            label="Total Invested", color="gray", linewidth=1.5, linestyle="--")

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Portfolio Value (KRW)", fontsize=12)
    ax.set_title(
        f"S&P 500 Investment Strategy Comparison  ({START_DATE} ~ {END_DATE},  {DAILY_KRW:,} KRW/day)",
        fontsize=13,
    )
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)

    last_date = data.index[-1]
    for col, color, va in [("strat1", "steelblue", "bottom"), ("strat2", "tomato", "top")]:
        val = data[col].iloc[-1]
        ax.annotate(
            f"{val:,.0f} KRW",
            xy=(last_date, val),
            xytext=(8, 0),
            textcoords="offset points",
            color=color,
            fontsize=9,
            va=va,
        )

    plt.tight_layout()
    plt.savefig("sp500_strategy.png", dpi=150)
    print("차트 저장 완료: sp500_strategy.png")
    try:
        plt.show()
    except Exception:
        pass


def print_summary(data: pd.DataFrame, fx_source: str) -> None:
    n = len(data)
    total_inv = DAILY_KRW * n
    s1 = data["strat1"].iloc[-1]
    s2 = data["strat2"].iloc[-1]
    r1 = (s1 - total_inv) / total_inv * 100
    r2 = (s2 - total_inv) / total_inv * 100

    print("\n" + "=" * 62)
    print(f"{'항목':<26} {'전략1: 매일매수':>16} {'전략2: 하락매수':>16}")
    print("=" * 62)
    print(f"{'거래일 수 (Trading Days)':<26} {n:>16d} {n:>16d}")
    print(f"{'총 투자금 (KRW)':<26} {total_inv:>16,.0f} {total_inv:>16,.0f}")
    print(f"{'최종 잔고 (KRW)':<26} {s1:>16,.0f} {s2:>16,.0f}")
    print(f"{'수익률 (Return %)':<26} {r1:>15.2f}% {r2:>15.2f}%")
    print("=" * 62)
    print(f"환율 소스: {fx_source}")
    print(f"데이터 기간: {data.index[0].date()} ~ {data.index[-1].date()}")


def main() -> None:
    print("데이터 로딩 중...")
    data, fx_source = build_data()
    print(f"S&P 500 데이터: {len(data)}거래일 로드 완료 (환율 소스: {fx_source})")

    data = simulate(data)
    plot_results(data, fx_source)
    print_summary(data, fx_source)


if __name__ == "__main__":
    main()
