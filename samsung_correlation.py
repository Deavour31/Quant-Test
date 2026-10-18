"""삼성전자와 미국 시장(QQQ/TQQQ)·반도체(SOXX)·이 전략(보조 자금)의 상관이 시기별로 바뀌었나

한국/미국은 장 시간이 달라 일간 수익률은 어긋난다 → 주간 수익률(금요일 종가 기준)로도 본다.
삼성전자는 원화, 미국 자산은 원화 환산(환율 반영)으로 계산한다.
"""

import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder
from tqqq_chart import START, simulate


def px(t: str) -> pd.Series:
    return yf.download(t, start=START, auto_adjust=True, progress=False)["Close"].squeeze().dropna()


def main() -> None:
    pd.set_option("display.width", 200)
    tq = px("TQQQ")
    rsi = rsi_wilder(tq)
    ok = rsi.notna()
    tq, rsi = tq[ok], rsi[ok]
    idx = tq.index
    fx = px("KRW=X").reindex(idx).ffill().bfill()
    if fx.median() < 1:
        fx = 1 / fx
    ss = px("005930.KS").reindex(idx).ffill().bfill()
    qq = px("QQQ").reindex(idx).ffill() * fx
    sx = px("SOXX").reindex(idx).ffill() * fx
    tqk = tq * fx
    _, sleeve = simulate(tqk, rsi)

    df = pd.DataFrame({"삼성전자": ss, "QQQ": qq, "SOXX(반도체)": sx, "TQQQ": tqk, "전략(보조)": sleeve})
    wk = df.resample("W-FRI").last().pct_change().dropna()
    dl = df.pct_change().dropna()
    dl_lag = pd.concat([dl["삼성전자"], dl[["QQQ", "SOXX(반도체)", "TQQQ"]].shift(1)], axis=1).dropna()  # 미국 전일 → 한국 당일

    def table(frame, ref_cols, label):
        rows = []
        for y, g in frame.groupby(frame.index.year):
            rows.append(dict(연도=y, **{c: round(g["삼성전자"].corr(g[c]), 2) for c in ref_cols}))
        g = frame[frame.index.year <= 2024]
        rows.append(dict(연도="2017-24", **{c: round(g["삼성전자"].corr(g[c]), 2) for c in ref_cols}))
        g = frame[frame.index.year >= 2025]
        rows.append(dict(연도="2025-26", **{c: round(g["삼성전자"].corr(g[c]), 2) for c in ref_cols}))
        print(f"\n=== {label} ===")
        print(pd.DataFrame(rows).to_string(index=False))

    table(wk, ["QQQ", "SOXX(반도체)", "TQQQ", "전략(보조)"], "삼성전자 vs 미국 자산 / 전략 — 주간 수익률 상관 (원화 환산)")
    table(dl_lag, ["QQQ", "SOXX(반도체)", "TQQQ"], "삼성전자 당일 vs 미국 전일 — 일간 수익률 상관 (장 시간 보정)")

    print("\n=== 연도별 수익률 (원화 환산) ===")
    yr = df.resample("YE").last().pct_change().dropna() * 100
    yr.index = yr.index.year
    print(yr.round(0).astype(int).to_string())


if __name__ == "__main__":
    main()
