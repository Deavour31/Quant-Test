"""TQQQ RSI 분할매수 전략: 매도 조건 역추적 백테스트

매수: 일봉 RSI(14) <= 33.5 → 1차, <= 29.5 → 2차 (각 50%), 3차 없음, 손절 없음
매도: 후보 규칙을 그리드로 돌려 공개된 통계와 비교
타깃 통계: 거래 수익 확률 96.88% (=31/32), 평균 수익률 +8.12%, 평균 보유 4.53거래일
"""

import itertools

import numpy as np
import pandas as pd
import yfinance as yf

RSI_BUY_1, RSI_BUY_2 = 33.5, 29.5
TARGET = dict(n=32, win=96.88, ret=8.12, hold=4.53)


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def load(start: str) -> pd.DataFrame:
    df = yf.download("TQQQ", start=start, auto_adjust=True, progress=False)
    close = df["Close"].squeeze()
    out = pd.DataFrame({"close": close})
    out["rsi"] = rsi_wilder(close)
    for n in (5, 10, 20):
        out[f"ma{n}"] = close.rolling(n).mean()
    return out.dropna()


def backtest(df: pd.DataFrame, exit_rule, profit_only: bool):
    """exit_rule(row, avg_cost) -> bool. 종가 기준 체결. 손절 없음."""
    close, rsi = df["close"].values, df["rsi"].values
    trades, pos = [], None  # pos: dict(cost, shares, tranche, entry_i)
    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= RSI_BUY_1:
                pos = dict(cash=0.5, shares=0.5 / close[i], t2=False, i0=i)
                if rsi[i] <= RSI_BUY_2:
                    pos["cash"] += 0.5
                    pos["shares"] += 0.5 / close[i]
                    pos["t2"] = True
            continue
        if not pos["t2"] and rsi[i] <= RSI_BUY_2:
            pos["cash"] += 0.5
            pos["shares"] += 0.5 / close[i]
            pos["t2"] = True
        avg = pos["cash"] / pos["shares"]
        row = df.iloc[i]
        hit = exit_rule(row, avg)
        if hit and (not profit_only or close[i] > avg):
            # 투입금 대비 수익률 (1차만 들어갔으면 투입금 50% 기준)
            trades.append((close[i] / avg - 1, i - pos["i0"], df.index[pos["i0"]]))
            pos = None
    open_pos = None
    if pos is not None:
        avg = pos["cash"] / pos["shares"]
        open_pos = (close[-1] / avg - 1, len(df) - 1 - pos["i0"], df.index[pos["i0"]])
    return trades, open_pos


def stats(trades, open_pos):
    if not trades:
        return None
    r = np.array([t[0] for t in trades])
    h = np.array([t[1] for t in trades])
    n_all = len(trades) + (1 if open_pos else 0)
    wins = (r > 0).sum() + (1 if open_pos and open_pos[0] > 0 else 0)
    return dict(n=n_all, win=wins / n_all * 100, ret=r.mean() * 100, hold=h.mean(),
                open=open_pos)


def candidates():
    for p in np.arange(0.03, 0.201, 0.01):
        yield f"TP +{p*100:.0f}%", (lambda row, avg, p=p: row["close"] >= avg * (1 + p))
    for r in range(40, 81, 5):
        yield f"RSI>={r}", (lambda row, avg, r=r: row["rsi"] >= r)
    for n in (5, 10, 20):
        yield f"close>=MA{n}", (lambda row, avg, n=n: row["close"] >= row[f"ma{n}"])


def distance(s):
    # 거래수는 기간 의존이 커서 가중치를 낮게
    return (abs(s["win"] - TARGET["win"]) / 3
            + abs(s["ret"] - TARGET["ret"]) / 2
            + abs(s["hold"] - TARGET["hold"]) / 1.5
            + abs(s["n"] - TARGET["n"]) / 16)


def main():
    rows = []
    for start in ("2010-01-01", "2015-01-01", "2018-01-01", "2019-01-01"):
        df = load(start)
        for name, rule in candidates():
            for profit_only in (True, False):
                trades, open_pos = backtest(df, rule, profit_only)
                s = stats(trades, open_pos)
                if s is None:
                    continue
                rows.append(dict(start=start[:4], rule=name, profit_only=profit_only,
                                 **{k: v for k, v in s.items() if k != "open"},
                                 open=("Y" if s["open"] else ""), dist=distance(s)))
    res = pd.DataFrame(rows).sort_values("dist")
    pd.set_option("display.width", 200)
    print(f"타깃: {TARGET}\n")
    print(res.head(25).round(2).to_string(index=False))
    res.to_csv("tqqq_backtest_results.csv", index=False)


if __name__ == "__main__":
    main()
