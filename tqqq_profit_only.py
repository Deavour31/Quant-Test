"""RSI>=40이어도 평단 아래면 존버(수익일 때만 매도) vs 기존(RSI>=40이면 무조건 매도)

QQQ(나스닥100) 포지션 단위 레버리지 토큰, 격리마진, 유지증거금 1%, 펀딩 0. 신호는 tqqq_levtoken과 동일.
종료 시점에 열려 있는 포지션은 마지막 종가로 평가해 포함(OPEN 표시).
"""

import pandas as pd

from tqqq_levtoken import B1, B2, EX, MM, build


def run(df, L, profit_only, stop=None):
    o, lo, c, rsi = (df[k].values for k in ("Open", "Low", "Close", "rsi"))
    idx = df.index
    out, pos = [], None

    def add(p, price, m):
        u = L * m / price
        p["M"] += m; p["u"] += u; p["N"] += u * price

    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= B1:
                pos = dict(M=0.0, u=0.0, N=0.0, t2=False, i0=i, mae=0.0)
                add(pos, c[i], 0.5)
                if rsi[i] <= B2:
                    add(pos, c[i], 0.5); pos["t2"] = True
            continue
        a = pos["N"] / pos["u"]
        p_liq = a * (1 - 1 / L) / (1 - MM) if L > 1 else 0.0
        pos["mae"] = min(pos["mae"], lo[i] / a - 1)
        if lo[i] <= p_liq:
            fill = min(p_liq, o[i])
            out.append(dict(entry=idx[pos["i0"]], pnl=max(pos["u"] * (fill - a), -pos["M"]),
                            hold=i - pos["i0"], mae=pos["mae"], liq=True, open=False, stopped=False))
            pos = None
            continue
        if not pos["t2"] and rsi[i] <= B2:
            add(pos, c[i], 0.5); pos["t2"] = True
            a = pos["N"] / pos["u"]
        if stop is not None and c[i] / a - 1 <= stop:   # 평단 대비 지수 하락률 손절 (종가)
            out.append(dict(entry=idx[pos["i0"]], pnl=pos["u"] * (c[i] - a), hold=i - pos["i0"],
                            mae=pos["mae"], liq=False, open=False, stopped=True))
            pos = None
            continue
        if rsi[i] >= EX and (not profit_only or c[i] > a):
            out.append(dict(entry=idx[pos["i0"]], pnl=pos["u"] * (c[i] - a), hold=i - pos["i0"],
                            mae=pos["mae"], liq=False, open=False, stopped=False))
            pos = None
    if pos is not None:
        a = pos["N"] / pos["u"]
        out.append(dict(entry=idx[pos["i0"]], pnl=max(pos["u"] * (c[-1] - a), -pos["M"]),
                        hold=len(df) - 1 - pos["i0"], mae=pos["mae"], liq=False, open=True, stopped=False))
    return pd.DataFrame(out)


def summ(name, L, t):
    eq = (1 + t.pnl).prod()
    return dict(rule=name, L=f"{L}x", n=len(t), liq=int(t.liq.sum()), stops=int(t.stopped.sum()), open=int(t.open.sum()),
                win=(t.pnl > 0).mean() * 100, avg_hold=t.hold.mean(), max_hold=int(t.hold.max()),
                worst_mae=t.mae.min() * 100, worst_pnl=t.pnl.min() * 100, compound_x=eq)


def main():
    pd.set_option("display.width", 220)
    real, stress = build()
    for title, df in [("실제 QQQ 2010~현재", real), ("스트레스 나스닥100 1986~2010", stress)]:
        rows = []
        for L in (2, 3):
            rows.append(summ("RSI40 무조건 매도", L, run(df, L, False)))
            rows.append(summ("RSI40 & 수익일 때만(존버)", L, run(df, L, True)))
        print(f"\n=== {title} ===")
        print(pd.DataFrame(rows).round(2).to_string(index=False))

    t = run(stress, 3, True)
    print("\n--- 스트레스 3x 존버: 오래 보유/청산된 거래 TOP ---")
    print(t.sort_values("hold", ascending=False).head(6).assign(
        pnl=lambda x: (x.pnl * 100).round(1), mae=lambda x: (x.mae * 100).round(1)).to_string(index=False))


if __name__ == "__main__":
    main()
