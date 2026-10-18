"""기준 전략을 실제 TQQQ 일봉(Yahoo, 분할/배당 조정)에 적용해 거래 지점을 차트로 표시

기준: RSI(14,Wilder) <= 33.5 1차 50% / <= 29.5 2차 50% / RSI >= 40 무조건 전량 매도 / 손절 없음 / 종가 체결
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder

START = "2017-01-01"
B1, B2, EX = 33.5, 29.5, 40.0


def simulate(close: pd.Series, rsi: pd.Series):
    c, r, idx = close.values, rsi.values, close.index
    trades, eq, base, pos = [], np.ones(len(c)), 1.0, None
    for i in range(len(c)):
        if pos is None:
            if r[i] <= B1:
                pos = dict(i0=i, cash=0.5, sh=0.5 / c[i], b2=None, low=c[i])
                if r[i] <= B2:
                    pos["cash"] += 0.5; pos["sh"] += 0.5 / c[i]; pos["b2"] = i
            eq[i] = base
            continue
        if pos["b2"] is None and r[i] <= B2:
            pos["cash"] += 0.5; pos["sh"] += 0.5 / c[i]; pos["b2"] = i
        avg = pos["cash"] / pos["sh"]
        pos["low"] = min(pos["low"], c[i])
        pnl = pos["sh"] * c[i] - pos["cash"]          # 자본(=1) 대비 손익
        eq[i] = base * (1 + pnl)
        if r[i] >= EX:
            trades.append(dict(buy1=idx[pos["i0"]], p1=c[pos["i0"]], rsi1=r[pos["i0"]],
                               buy2=idx[pos["b2"]] if pos["b2"] is not None else None,
                               p2=c[pos["b2"]] if pos["b2"] is not None else np.nan,
                               avg=avg, sell=idx[i], sell_p=c[i], hold=i - pos["i0"],
                               ret=c[i] / avg - 1, worst=pos["low"] / avg - 1, cap=pnl))
            base *= 1 + pnl
            pos = None
    return pd.DataFrame(trades), pd.Series(eq, index=idx)


def main() -> None:
    raw = yf.download("TQQQ", start=START, auto_adjust=True, progress=False)
    close = raw["Close"].squeeze().dropna()
    rsi = rsi_wilder(close)
    ok = rsi.notna()
    close, rsi = close[ok], rsi[ok]
    t, eq = simulate(close, rsi)

    n = len(t)
    print(f"데이터: TQQQ {close.index[0].date()} ~ {close.index[-1].date()} ({len(close)}거래일, Yahoo 조정종가)")
    print(f"거래 {n}건 | 수익 확률 {(t.ret > 0).mean() * 100:.2f}% | 평균 수익률 {t.ret.mean() * 100:.2f}% | "
          f"평균 보유 {t.hold.mean():.2f}거래일 | 최악 {t.ret.min() * 100:.1f}%")
    bh = close / close.iloc[0]
    yrs = (close.index[-1] - close.index[0]).days / 365.25
    print(f"전략(자본 100% 운용, 평가손익 포함): {eq.iloc[-1]:.2f}배 (연 {(eq.iloc[-1] ** (1 / yrs) - 1) * 100:.1f}%, "
          f"최대낙폭 {(eq / eq.cummax() - 1).min() * 100:.1f}%)")
    print(f"TQQQ 단순보유: {bh.iloc[-1]:.2f}배 (연 {(bh.iloc[-1] ** (1 / yrs) - 1) * 100:.1f}%, "
          f"최대낙폭 {(bh / bh.cummax() - 1).min() * 100:.1f}%)")

    out = t.copy()
    for col in ("buy1", "buy2", "sell"):
        out[col] = out[col].dt.strftime("%Y-%m-%d").fillna("-")
    out["ret"] = (out.ret * 100).round(1); out["worst"] = (out.worst * 100).round(1)
    out["cap"] = (out.cap * 100).round(1)
    out = out.round(2)
    out.to_csv("tqqq_chart_trades.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
    print(out[["buy1", "p1", "rsi1", "buy2", "avg", "sell", "sell_p", "hold", "ret", "worst"]].to_string(index=False))

    fig, ax = plt.subplots(3, 1, figsize=(17, 13), sharex=True,
                           gridspec_kw=dict(height_ratios=[3.2, 1.3, 1.8]), constrained_layout=True)
    ax[0].plot(close.index, close, color="#333", lw=1.0)
    ax[0].set_yscale("log")
    ax[0].scatter(t.buy1, t.p1, marker="^", s=55, color="#1a9850", zorder=3, label="Buy 1 (RSI<=33.5)")
    t2 = t.dropna(subset=["buy2"])
    ax[0].scatter(t2.buy2, t2.p2, marker="^", s=55, color="#00441b", zorder=3, label="Buy 2 (RSI<=29.5)")
    win, loss = t[t.ret > 0], t[t.ret <= 0]
    ax[0].scatter(win.sell, win.sell_p, marker="v", s=55, color="#d73027", zorder=3, label="Sell (RSI>=40, profit)")
    ax[0].scatter(loss.sell, loss.sell_p, marker="X", s=110, color="black", zorder=4, label="Sell (RSI>=40, LOSS)")
    for _, r_ in loss.iterrows():
        ax[0].annotate(f"loss {r_.ret * 100:.1f}%\n(entry {r_.buy1:%Y-%m-%d})", (r_.sell, r_.sell_p),
                       xytext=(10, -40), textcoords="offset points", fontsize=9,
                       arrowprops=dict(arrowstyle="-", color="gray"))
    ax[0].set_ylabel("TQQQ price (log, split-adjusted)")
    ax[0].set_title(f"TQQQ real daily data - RSI split-buy strategy: {n} trades, win {(t.ret > 0).mean() * 100:.1f}%, "
                    f"avg {t.ret.mean() * 100:.2f}%, avg hold {t.hold.mean():.2f} days")
    ax[0].legend(loc="upper left"); ax[0].grid(alpha=0.3)

    ax[1].plot(rsi.index, rsi, color="#4575b4", lw=0.8)
    for y, col in ((B1, "#1a9850"), (B2, "#00441b"), (EX, "#d73027")):
        ax[1].axhline(y, color=col, ls="--", lw=0.9)
    ax[1].text(rsi.index[5], B1 + 1, "33.5", color="#1a9850"); ax[1].text(rsi.index[5], B2 - 5, "29.5", color="#00441b")
    ax[1].text(rsi.index[5], EX + 1, "40 (sell)", color="#d73027")
    ax[1].set_ylabel("RSI(14)"); ax[1].set_ylim(5, 95); ax[1].grid(alpha=0.3)

    ax[2].plot(eq.index, eq, color="#d73027", lw=1.4, label="Strategy (all capital, mark-to-market, cash idle 0%)")
    ax[2].plot(bh.index, bh, color="gray", lw=1.1, label="TQQQ buy & hold")
    ax[2].set_yscale("log"); ax[2].set_ylabel("Growth of 1 (log)")
    ax[2].legend(loc="upper left"); ax[2].grid(alpha=0.3)

    fig.savefig("tqqq_chart.png", dpi=120)
    print("\n저장: tqqq_chart.png, tqqq_chart_trades.csv")


if __name__ == "__main__":
    main()
