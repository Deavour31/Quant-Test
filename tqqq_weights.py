"""1차:2차 매수 비중별 비교 (RSI 33.5/29.5 매수, RSI>=40 매도, 손절 없음)"""

import numpy as np
import pandas as pd

from tqqq_backtest import load
from tqqq_robustness import run, summarize


def main() -> None:
    pd.set_option("display.width", 200)
    df = load("2010-01-01")
    rows = []
    for label, w1 in [("1:1", 1 / 2), ("1:2", 1 / 3), ("1:3", 1 / 4), ("2:1", 2 / 3), ("전액 1차", 1.0)]:
        t = run(df, 33.5, 29.5, 40.0, w1=w1)
        s = summarize(t)
        rows.append(dict(
            split=label, n=s["n"], win=s["win"],
            ret_invested=s["ret"], ret_capital=t.ret_cap.mean() * 100,
            sum_capital=t.ret_cap.sum() * 100, avg_deployed=t.deployed.mean() * 100,
            two_tranche_pct=t.two.mean() * 100, worst=s["worst"], mae=s["mae"],
            worst_cap_pnl=t.ret_cap.min() * 100,
        ))
    print("=== 전체 2010~현재 ===")
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    rows = []
    for label, w1 in [("1:1", 1 / 2), ("1:2", 1 / 3)]:
        t = run(df, 33.5, 29.5, 40.0, w1=w1)
        for name, a, b in [("2010-2016", "2010", "2016"), ("2017-2022", "2017", "2022"), ("2023-현재", "2023", "2030")]:
            sub = t[(t.entry >= f"{a}-01-01") & (t.entry <= f"{b}-12-31")]
            rows.append(dict(split=label, period=name, n=len(sub), win=(sub.ret > 0).mean() * 100,
                             ret_invested=sub.ret.mean() * 100, ret_capital=sub.ret_cap.mean() * 100,
                             mae=sub.mae.min() * 100))
    print("\n=== 기간별 1:1 vs 1:2 ===")
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    print("\n=== 2차까지 간 거래만 (1:1 vs 1:2) ===")
    for label, w1 in [("1:1", 1 / 2), ("1:2", 1 / 3)]:
        t = run(df, 33.5, 29.5, 40.0, w1=w1)
        for k, g in t.groupby("two"):
            print(f"{label} 2차 {'진입' if k else '미진입'}: n={len(g)} 투입금수익 {g.ret.mean()*100:.2f}% "
                  f"자본수익 {g.ret_cap.mean()*100:.2f}% 평균보유 {g.hold.mean():.2f}일 최악낙폭 {g.mae.min():.1%}")


if __name__ == "__main__":
    main()
