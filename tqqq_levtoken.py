"""QQQ 레버리지 토큰(포지션 단위 배수, 일일 리셋 없음)으로 같은 RSI 전략을 돌리면?

신호: TQQQ 일봉 RSI(14) <= 33.5 (1차 50%) / <= 29.5 (2차 50%), RSI >= 40 매도 (원 전략과 동일 타이밍)
체결: 신호일 종가. 거래 대상은 QQQ(2010~) 또는 나스닥100 지수(1986~2010, 합성 구간)
레버리지: 증거금 M, 명목 N = L*M. 격리마진, 일중 저가가 청산가에 닿으면 청산(손실은 증거금 한도).
펀딩비: 명목가치에 연 FUNDING 적용(보유 일수 비례). 정확한 값은 거래소/토큰마다 다르므로 민감도로 본다.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder

B1, B2, EX = 33.5, 29.5, 40.0
MM = 0.01  # 유지증거금률 가정
COST_3X = 0.0095 + 2 * 0.03


def dl(t, start):
    df = yf.download(t, start=start, auto_adjust=True, progress=False)
    df.columns = df.columns.get_level_values(0)
    return df


def build():
    ndx = dl("^NDX", "1985-10-01")
    r = ndx["Close"].pct_change().dropna()
    syn3 = (1 + 3 * r - COST_3X / 252).clip(lower=0).cumprod() * 100
    syn_rsi = rsi_wilder(syn3)
    tq = dl("TQQQ", "2010-01-01")["Close"]
    tq_rsi = rsi_wilder(tq)
    qqq = dl("QQQ", "2010-01-01")
    real = qqq.join(tq_rsi.rename("rsi"), how="inner").dropna()
    stress = ndx.join(syn_rsi.rename("rsi"), how="inner").dropna()
    stress = stress[stress.index < "2010-02-01"]
    return real, stress


def run(df, L, funding):
    o, lo, c, rsi = (df[k].values for k in ("Open", "Low", "Close", "rsi"))
    idx = df.index
    out, pos = [], None

    def add(pos, price, m):
        u = L * m / price
        pos["M"] += m; pos["u"] += u; pos["N"] += u * price

    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= B1:
                pos = dict(M=0.0, u=0.0, N=0.0, t2=False, i0=i)
                add(pos, c[i], 0.5)
                if rsi[i] <= B2:
                    add(pos, c[i], 0.5); pos["t2"] = True
            continue
        a = pos["N"] / pos["u"]
        p_liq = a * (1 - 1 / L) / (1 - MM) if L > 1 else 0.0
        days = (idx[i] - idx[pos["i0"]]).days
        if lo[i] <= p_liq:                       # 청산 (갭이면 시가 체결, 손실은 증거금 한도)
            fill = min(p_liq, o[i])
            pnl = max(pos["u"] * (fill - a), -pos["M"])
            out.append(dict(entry=idx[pos["i0"]], pnl=pnl, M=pos["M"], hold=i - pos["i0"], liq=True))
            pos = None
            continue
        if not pos["t2"] and rsi[i] <= B2:
            add(pos, c[i], 0.5); pos["t2"] = True
            a = pos["N"] / pos["u"]
        if rsi[i] >= EX:
            pnl = pos["u"] * (c[i] - a) - funding * pos["N"] * days / 365
            out.append(dict(entry=idx[pos["i0"]], pnl=max(pnl, -pos["M"]), M=pos["M"],
                            hold=i - pos["i0"], liq=False))
            pos = None
    return pd.DataFrame(out)


def summ(L, t):
    return dict(L=f"{L}x", n=len(t), liq=int(t.liq.sum()),
                win=(t.pnl > 0).mean() * 100,
                ret_margin=(t.pnl / t.M).mean() * 100,
                cap_per_trade=t.pnl.mean() * 100, cap_sum=t.pnl.sum() * 100,
                worst_cap=t.pnl.min() * 100, hold=t.hold.mean(),
                compound_x=(1 + t.pnl).prod())


def main():
    pd.set_option("display.width", 220)
    real, stress = build()
    for name, df in [("실제 QQQ 2010~현재", real), ("스트레스: 나스닥100 1986~2010 (1987·닷컴·2008)", stress)]:
        for f in (0.0, 0.10):
            print(f"\n=== {name} | 펀딩 연 {f:.0%} ===")
            rows = [summ(L, run(df, L, f)) for L in (1, 2, 3, 5, 10)]
            print(pd.DataFrame(rows).round(2).to_string(index=False))
    t = run(stress, 3, 0.0)
    print("\n--- 스트레스 3x 청산 거래 ---")
    print(t[t.liq].assign(pnl=lambda x: (x.pnl * 100).round(1)).to_string(index=False))


if __name__ == "__main__":
    main()
