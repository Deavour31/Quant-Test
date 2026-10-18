"""거래 수익률 곱(compound_x)은 시간을 무시한다 → 일별 자산곡선(평가손익 포함)으로 연환산·최대낙폭 비교

tqqq_profit_only.run과 동일한 규칙. 포지션이 없는 동안 현금은 이자 0%로 가정.
자본의 100%를 증거금 한도로 매 거래 재투자(1차 50%, 2차 50%). 벤치마크: 기초지수 1x 단순보유.
"""

import numpy as np
import pandas as pd

from tqqq_levtoken import B1, B2, EX, MM, build


def equity_curve(df, L, profit_only):
    o, lo, c, rsi = (df[k].values for k in ("Open", "Low", "Close", "rsi"))
    n = len(df)
    eq = np.ones(n)
    base, pos = 1.0, None
    in_pos = np.zeros(n, dtype=bool)

    def add(p, price, m):
        u = L * m / price
        p["M"] += m; p["u"] += u; p["N"] += u * price

    for i in range(n):
        if pos is None:
            if rsi[i] <= B1:
                pos = dict(M=0.0, u=0.0, N=0.0, t2=False)
                add(pos, c[i], 0.5)
                if rsi[i] <= B2:
                    add(pos, c[i], 0.5); pos["t2"] = True
                in_pos[i] = True
            eq[i] = base
            continue
        in_pos[i] = True
        a = pos["N"] / pos["u"]
        p_liq = a * (1 - 1 / L) / (1 - MM) if L > 1 else 0.0
        if lo[i] <= p_liq:
            pnl = max(pos["u"] * (min(p_liq, o[i]) - a), -pos["M"])
            base *= 1 + pnl; eq[i] = base; pos = None
            continue
        if not pos["t2"] and rsi[i] <= B2:
            add(pos, c[i], 0.5); pos["t2"] = True
            a = pos["N"] / pos["u"]
        pnl = pos["u"] * (c[i] - a)
        eq[i] = base * (1 + pnl)
        if rsi[i] >= EX and (not profit_only or c[i] > a):
            base *= 1 + pnl; pos = None
    return pd.Series(eq, index=df.index), in_pos.mean()


def stats(eq: pd.Series):
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0]
    cagr = total ** (1 / years) - 1 if total > 0 else -1.0
    mdd = (eq / eq.cummax() - 1).min()
    return total, cagr * 100, mdd * 100, years


def main():
    pd.set_option("display.width", 200)
    real, stress = build()
    for title, df in [("스트레스 나스닥100 1986~2010", stress), ("실제 QQQ 2010~현재", real)]:
        rows = []
        bh = df["Close"] / df["Close"].iloc[0]
        t, cg, md, yrs = stats(bh)
        rows.append(dict(strategy="지수 1x 단순보유", total_x=t, cagr_pct=cg, mdd_pct=md, in_market_pct=100.0))
        for L in (2, 3):
            for name, po in (("RSI40 무조건 매도", False), ("존버(수익일 때만 매도)", True)):
                e, frac = equity_curve(df, L, po)
                t, cg, md, _ = stats(e)
                rows.append(dict(strategy=f"{L}x {name}", total_x=t, cagr_pct=cg, mdd_pct=md,
                                 in_market_pct=frac * 100))
        print(f"\n=== {title} ({yrs:.1f}년) ===")
        print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
