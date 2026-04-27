"""10개 종목 × 2전략 비교: 매일 매수 vs 하락 시 집중 매수"""

import sys
import subprocess

for _pkg in ["yfinance", "pandas", "matplotlib"]:
    try:
        __import__(_pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg, "-q"])

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec

# ── 상수 ──────────────────────────────────────────────────────────────────────
START_DATE  = "2025-04-27"
END_DATE    = "2026-04-27"
DAILY_KRW   = 5_000
FALLBACK_FX = 1_370.0

# ── 10개 종목 (다양한 특성) ────────────────────────────────────────────────────
TICKERS = {
    "^GSPC":   ("S&P 500",         "Broad Market Index",      "#4878cf"),
    "QQQ":     ("Nasdaq 100",      "Tech-Heavy Growth ETF",   "#6acc65"),
    "AAPL":    ("Apple",           "Mega-Cap Stable Tech",    "#d65f5f"),
    "TSLA":    ("Tesla",           "High-Volatility Growth",  "#b47cc7"),
    "BRK-B":   ("Berkshire B",     "Value / Conglomerate",    "#c4ad66"),
    "GLD":     ("Gold ETF",        "Safe Haven / Commodity",  "#f5c542"),
    "TLT":     ("Long Bond ETF",   "20yr Treasury (Bonds)",   "#77bedb"),
    "VYM":     ("Dividend ETF",    "High Dividend Yield",     "#e8926e"),
    "VWO":     ("Emerging Mkt",    "Developing Countries ETF","#92c063"),
    "BTC-USD": ("Bitcoin",         "Crypto / Extreme Volatil","#f7931a"),
}

# ── 환율 로드 ─────────────────────────────────────────────────────────────────
def load_fx(start: str, end: str) -> pd.Series:
    for ticker in ("KRW=X", "KRWUSD=X"):
        try:
            df = yf.download(ticker, start=start, end=end,
                             auto_adjust=True, progress=False)
            if df is not None and not df.empty:
                s = df["Close"].squeeze().dropna()
                if not s.empty:
                    median = s.median()
                    return (1.0 / s) if median < 1 else s
        except Exception:
            continue
    return pd.Series(dtype=float)   # 빈 시리즈 → fallback


def align_fx(fx_raw: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    if fx_raw.empty:
        return pd.Series(FALLBACK_FX, index=index)
    return fx_raw.reindex(index).ffill().bfill().fillna(FALLBACK_FX)


# ── 단일 종목 데이터 로드 ─────────────────────────────────────────────────────
def load_price(ticker: str, start: str, end: str) -> pd.Series:
    df = yf.download(ticker, start=start, end=end,
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    s = df["Close"].squeeze()
    return s.dropna()


# ── 전략 시뮬레이션 ───────────────────────────────────────────────────────────
def simulate(price: pd.Series, fx: pd.Series) -> pd.DataFrame:
    closes = price.values
    fxs    = fx.values
    n      = len(closes)

    strat1         = [0.0] * n
    strat2         = [0.0] * n
    total_invested = [0.0] * n

    # 전략1: 매일 매수
    shares1 = 0.0
    for i in range(n):
        shares1 += (DAILY_KRW / fxs[i]) / closes[i]
        strat1[i]         = shares1 * closes[i] * fxs[i]
        total_invested[i] = DAILY_KRW * (i + 1)

    # 전략2: 하락·보합일에 모은 현금 전부 매수
    shares2, cash = 0.0, 0.0
    for i in range(n):
        cash += DAILY_KRW
        if i == 0 or closes[i] <= closes[i - 1]:
            shares2 += (cash / fxs[i]) / closes[i]
            cash = 0.0
        strat2[i] = shares2 * closes[i] * fxs[i] + cash

    return pd.DataFrame({
        "strat1":         strat1,
        "strat2":         strat2,
        "total_invested": total_invested,
    }, index=price.index)


# ── 메인 루프 ─────────────────────────────────────────────────────────────────
def run_all() -> dict[str, pd.DataFrame]:
    print("환율 데이터 로딩 중...")
    fx_raw = load_fx(START_DATE, END_DATE)
    fx_src = "KRW=X" if not fx_raw.empty else "fallback(1370)"
    print(f"  환율 소스: {fx_src}")

    results = {}
    for ticker, (name, desc, _) in TICKERS.items():
        print(f"  [{ticker:8s}] {name} 로딩 중...", end=" ")
        price = load_price(ticker, START_DATE, END_DATE)
        if price.empty:
            print("데이터 없음 — 건너뜀")
            continue
        fx    = align_fx(fx_raw, price.index)
        df    = simulate(price, fx)
        results[ticker] = df
        n        = len(df)
        inv      = DAILY_KRW * n
        r1       = (df["strat1"].iloc[-1] - inv) / inv * 100
        r2       = (df["strat2"].iloc[-1] - inv) / inv * 100
        print(f"{n}일  전략1: {r1:+.1f}%  전략2: {r2:+.1f}%")

    return results


# ── 시각화 ────────────────────────────────────────────────────────────────────
def plot(results: dict[str, pd.DataFrame]) -> None:
    tickers = [t for t in TICKERS if t in results]
    n_tickers = len(tickers)
    ncols = 5
    nrows = (n_tickers + ncols - 1) // ncols   # = 2

    # ── Figure 1: 개별 종목 시계열 (2×5 그리드) ──────────────────────────────
    fig1, axes = plt.subplots(nrows, ncols, figsize=(22, 9), constrained_layout=True)
    axes_flat  = axes.flatten()

    for idx, ticker in enumerate(tickers):
        ax   = axes_flat[idx]
        df   = results[ticker]
        name, desc, color = TICKERS[ticker]

        ax.plot(df.index, df["strat1"],
                label="Daily Buy",    color="steelblue",  linewidth=1.5)
        ax.plot(df.index, df["strat2"],
                label="Dip Buy",      color="tomato",     linewidth=1.5)
        ax.plot(df.index, df["total_invested"],
                label="Invested",     color="gray",       linewidth=1.0,
                linestyle="--", alpha=0.7)

        n   = len(df)
        inv = DAILY_KRW * n
        r1  = (df["strat1"].iloc[-1] - inv) / inv * 100
        r2  = (df["strat2"].iloc[-1] - inv) / inv * 100

        ax.set_title(f"{name}\n{desc}", fontsize=8.5, weight="bold")
        ax.set_xlabel("")
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{x/1e6:.2f}M" if x >= 1e6
                                  else f"{x/1e3:.0f}K"))
        ax.tick_params(axis="x", labelsize=7, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(alpha=0.25)

        # 수익률 텍스트 (우상단)
        ax.text(0.97, 0.97,
                f"Buy: {r1:+.1f}%\nDip: {r2:+.1f}%",
                transform=ax.transAxes,
                ha="right", va="top",
                fontsize=7.5,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

        if idx == 0:
            ax.legend(fontsize=7, loc="upper left")

    # 빈 서브플롯 숨기기
    for i in range(n_tickers, len(axes_flat)):
        axes_flat[i].set_visible(False)

    fig1.suptitle(
        f"S&P 500 Style Strategy Comparison Across 10 Assets\n"
        f"5,000 KRW/day  |  {START_DATE} ~ {END_DATE}",
        fontsize=13, weight="bold"
    )
    fig1.savefig("multi_strategy_detail.png", dpi=150)
    print("\n차트 저장: multi_strategy_detail.png")

    # ── Figure 2: 수익률 요약 바 차트 ──────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(14, 6))

    labels, r1_list, r2_list = [], [], []
    for ticker in tickers:
        df  = results[ticker]
        n   = len(df)
        inv = DAILY_KRW * n
        r1  = (df["strat1"].iloc[-1] - inv) / inv * 100
        r2  = (df["strat2"].iloc[-1] - inv) / inv * 100
        labels.append(TICKERS[ticker][0])
        r1_list.append(r1)
        r2_list.append(r2)

    x     = range(len(labels))
    width = 0.35

    bars1 = ax2.bar([i - width/2 for i in x], r1_list, width,
                    label="Strategy 1: Daily Buy",   color="steelblue", alpha=0.85)
    bars2 = ax2.bar([i + width/2 for i in x], r2_list, width,
                    label="Strategy 2: Dip Buy",     color="tomato",    alpha=0.85)

    ax2.axhline(0, color="black", linewidth=0.8)

    # 바 위에 수익률 표시
    for bar in bars1:
        v = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 v + (1.0 if v >= 0 else -2.5),
                 f"{v:+.1f}%", ha="center", va="bottom", fontsize=7.5, color="steelblue")
    for bar in bars2:
        v = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 v + (1.0 if v >= 0 else -2.5),
                 f"{v:+.1f}%", ha="center", va="bottom", fontsize=7.5, color="tomato")

    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("Return % (1 year)", fontsize=11)
    ax2.set_title(
        f"Return Comparison: Daily Buy vs Dip Buy  ({START_DATE} ~ {END_DATE},  5,000 KRW/day)",
        fontsize=12, weight="bold"
    )
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3)

    fig2.tight_layout()
    fig2.savefig("multi_strategy_summary.png", dpi=150)
    print("차트 저장: multi_strategy_summary.png")

    try:
        plt.show()
    except Exception:
        pass


# ── 요약 테이블 출력 ──────────────────────────────────────────────────────────
def print_summary(results: dict[str, pd.DataFrame]) -> None:
    print("\n" + "=" * 72)
    print(f"{'종목':<12} {'이름':<14} {'특성':<24} {'전략1':>8} {'전략2':>8} {'우위'}")
    print("=" * 72)

    for ticker, (name, desc, _) in TICKERS.items():
        if ticker not in results:
            continue
        df  = results[ticker]
        n   = len(df)
        inv = DAILY_KRW * n
        r1  = (df["strat1"].iloc[-1] - inv) / inv * 100
        r2  = (df["strat2"].iloc[-1] - inv) / inv * 100
        winner = "Dip >" if r2 > r1 else ("Daily >" if r1 > r2 else "동일")
        print(f"{ticker:<12} {name:<14} {desc:<24} {r1:>+7.1f}% {r2:>+7.1f}% {winner}")

    print("=" * 72)
    print(f"투자금: {DAILY_KRW:,} KRW/day  |  기간: {START_DATE} ~ {END_DATE}")


# ── 진입점 ────────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"=== 10개 종목 전략 비교 ({START_DATE} ~ {END_DATE}) ===\n")
    results = run_all()
    if not results:
        print("유효한 데이터가 없습니다.")
        return
    plot(results)
    print_summary(results)


if __name__ == "__main__":
    main()
