"""'손절 없음'이 정당한가: 나스닥100 3배 합성(1986~)으로 닷컴·2008 구간까지 검증

합성 TQQQ = 나스닥100 일수익률 x3 - 연 보수/금융비용(근사). 실제 TQQQ와 비교해 검증.
전략: 1:1 분할(RSI<=33.5 / <=29.5), RSI>=40 매도. 손절 유무/폭만 바꿔 비교.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder

COST_PER_YEAR = 0.0095 + 2 * 0.03  # 보수 0.95% + 2배 차입 금융비용 ~3% 근사


def synth_tqqq() -> pd.DataFrame:
    ndx = yf.download("^NDX", start="1985-10-01", auto_adjust=True, progress=False)["Close"].squeeze()
    r = ndx.pct_change().dropna()
    p = (1 + 3 * r - COST_PER_YEAR / 252).clip(lower=0.0).cumprod() * 100
    return pd.DataFrame({"close": p, "rsi": rsi_wilder(p)}).dropna()


def real_tqqq() -> pd.DataFrame:
    c = yf.download("TQQQ", start="2010-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
    return pd.DataFrame({"close": c, "rsi": rsi_wilder(c)}).dropna()


def run(df, stop=None, b1=33.5, b2=29.5, ex=40.0):
    """stop: 평단 대비 손절 비율(예 -0.2). None이면 손절 없음. 종가 기준."""
    close, rsi, idx = df["close"].values, df["rsi"].values, df.index
    out, pos = [], None
    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= b1:
                pos = dict(cash=0.5, sh=0.5 / close[i], t2=False, i0=i, mae=0.0)
                if rsi[i] <= b2:
                    pos["cash"] += 0.5; pos["sh"] += 0.5 / close[i]; pos["t2"] = True
            continue
        if not pos["t2"] and rsi[i] <= b2:
            pos["cash"] += 0.5; pos["sh"] += 0.5 / close[i]; pos["t2"] = True
        avg = pos["cash"] / pos["sh"]
        chg = close[i] / avg - 1
        pos["mae"] = min(pos["mae"], chg)
        reason = "rsi" if rsi[i] >= ex else ("stop" if stop is not None and chg <= stop else None)
        if reason:
            out.append(dict(entry=idx[pos["i0"]], ret=chg, hold=i - pos["i0"], mae=pos["mae"],
                            cap=pos["sh"] * close[i] - pos["cash"], reason=reason, open=False))
            pos = None
    if pos is not None:
        avg = pos["cash"] / pos["sh"]
        out.append(dict(entry=idx[pos["i0"]], ret=close[-1] / avg - 1, hold=len(df) - 1 - pos["i0"],
                        mae=min(pos["mae"], close[-1] / avg - 1),
                        cap=pos["sh"] * close[-1] - pos["cash"], reason="OPEN", open=True))
    return pd.DataFrame(out)


def row(label, t):
    closed = t[~t.open]
    return dict(case=label, n=len(t), win=(closed.ret > 0).mean() * 100, avg=closed.ret.mean() * 100,
                worst=t.ret.min() * 100, mae=t.mae.min() * 100, max_hold=t.hold.max(),
                sum_cap=t.cap.sum() * 100, stops=(t.reason == "stop").sum(),
                open=("Y" if t.open.any() else ""))


def main() -> None:
    pd.set_option("display.width", 220)
    syn, real = synth_tqqq(), real_tqqq()

    j = pd.DataFrame({"s": syn["close"], "r": real["close"]}).dropna()
    j = j / j.iloc[0]
    sr, rr = syn["close"].pct_change(), real["close"].pct_change()
    both = pd.concat([sr, rr], axis=1, keys=["s", "r"]).dropna()
    print("=== 합성 모델 검증 (2010~현재) ===")
    print(f"일수익률 상관 {both.s.corr(both.r):.4f}, 누적 배수 합성 {j.s.iloc[-1]:.1f}x vs 실제 {j.r.iloc[-1]:.1f}x\n")

    pre = syn[syn.index < "2010-02-01"]
    print(f"=== 합성 TQQQ 1986~2010 (닷컴·2008 포함), 최대 낙폭 {((pre.close/pre.close.cummax())-1).min():.1%} ===")
    rows = []
    for label, st in [("손절 없음", None), ("-15%", -0.15), ("-20%", -0.20), ("-30%", -0.30), ("-40%", -0.40)]:
        rows.append(row(label, run(pre, st)))
    print(pd.DataFrame(rows).round(1).to_string(index=False))

    t = run(pre, None)
    print("\n--- 손절 없음: 가장 깊게/오래 물린 거래 TOP 6 (1986~2010) ---")
    print(t.assign(ret=lambda x: (x.ret * 100).round(1), mae=lambda x: (x.mae * 100).round(1))
          .sort_values("mae").head(6)[["entry", "ret", "hold", "mae", "reason"]].to_string(index=False))

    print("\n=== 합성 전체(1986~현재) vs 실제 TQQQ(2010~현재) ===")
    rows = []
    for label, st in [("손절 없음", None), ("-20%", -0.20), ("-30%", -0.30)]:
        rows.append(dict(data="합성 1986~", **row(label, run(syn, st))))
        rows.append(dict(data="실제 2010~", **row(label, run(real, st))))
    print(pd.DataFrame(rows).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
