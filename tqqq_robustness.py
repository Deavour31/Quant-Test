"""TQQQ RSI 분할매수 전략 강건성 검증

1) 민감도: 1차 매수선 x 매도선 격자 (2차 매수선 = 1차 - 4)에서 성과가 유지되는가
2) 기간 분할: 2010-16 / 2017-22 / 2023-현재 에서 같은 파라미터의 성과
3) 평가손실: 진입 후 보유 중 최대 낙폭(MAE)
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tqqq_backtest import load

BASE = dict(b1=33.5, b2=29.5, ex=40.0)


def run(df: pd.DataFrame, b1: float, b2: float, ex: float, w1: float = 0.5) -> pd.DataFrame:
    """w1: 1차 매수 비중 (2차 = 1 - w1). ret은 투입금 대비, ret_cap은 총자본(=1) 대비."""
    w2 = 1 - w1
    close, rsi, idx = df["close"].values, df["rsi"].values, df.index
    out, pos = [], None
    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= b1:
                pos = dict(cash=w1, sh=w1 / close[i], t2=False, i0=i, mae=0.0)
                if rsi[i] <= b2:
                    pos["cash"] += w2
                    pos["sh"] += w2 / close[i]
                    pos["t2"] = True
            continue
        if not pos["t2"] and rsi[i] <= b2:
            pos["cash"] += w2
            pos["sh"] += w2 / close[i]
            pos["t2"] = True
        avg = pos["cash"] / pos["sh"]
        pos["mae"] = min(pos["mae"], close[i] / avg - 1)
        if rsi[i] >= ex:
            out.append(dict(entry=idx[pos["i0"]], ret=close[i] / avg - 1,
                            ret_cap=pos["sh"] * close[i] - pos["cash"],
                            hold=i - pos["i0"], mae=pos["mae"], deployed=pos["cash"],
                            two=pos["t2"]))
            pos = None
    return pd.DataFrame(out)


def summarize(t: pd.DataFrame) -> dict:
    if t.empty:
        return dict(n=0, win=np.nan, ret=np.nan, hold=np.nan, worst=np.nan, mae=np.nan)
    return dict(n=len(t), win=(t.ret > 0).mean() * 100, ret=t.ret.mean() * 100,
                hold=t.hold.mean(), worst=t.ret.min() * 100, mae=t.mae.min() * 100)


def sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for b1 in np.arange(30, 39.1, 1.0):
        for ex in np.arange(36, 50.1, 2.0):
            rows.append(dict(b1=b1, ex=ex, **summarize(run(df, b1, b1 - 4, ex))))
    return pd.DataFrame(rows)


def heatmaps(sens: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    for ax, col, title, fmt in [(axes[0], "win", "Win rate % (closed trades)", "{:.0f}"),
                                (axes[1], "ret", "Avg return %", "{:.1f}"),
                                (axes[2], "mae", "Worst drawdown while holding %", "{:.0f}")]:
        pv = sens.pivot(index="b1", columns="ex", values=col)
        im = ax.imshow(pv.values, aspect="auto", cmap="RdYlGn", origin="lower")
        ax.set_xticks(range(len(pv.columns)), [f"{c:.0f}" for c in pv.columns])
        ax.set_yticks(range(len(pv.index)), [f"{r:.1f}" for r in pv.index])
        for (y, x), v in np.ndenumerate(pv.values):
            ax.text(x, y, fmt.format(v), ha="center", va="center", fontsize=8)
        ax.set_xlabel("Exit RSI >=")
        ax.set_ylabel("Buy-1 RSI <=  (Buy-2 = Buy-1 - 4)")
        ax.set_title(title)
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig("tqqq_robustness.png", dpi=130)


def main() -> None:
    pd.set_option("display.width", 200)
    df = load("2010-01-01")

    print("=== 1) 민감도 (2010~현재 전체) — 기준 33.5 / 29.5 / 40 근처 ===")
    sens = sensitivity(df)
    near = sens[(sens.b1.between(31, 36)) & (sens.ex.between(38, 44))]
    print(near.round(2).to_string(index=False))
    heatmaps(sens)

    print("\n=== 2) 기간 분할 (기준 파라미터 33.5/29.5/40) ===")
    t = run(df, **{"b1": BASE["b1"], "b2": BASE["b2"], "ex": BASE["ex"]})
    rows = []
    for name, a, b in [("2010-2016 (미검증)", "2010", "2016"),
                       ("2017-2022 (추정 표본)", "2017", "2022"),
                       ("2023-현재 (이후)", "2023", "2030"),
                       ("전체", "2010", "2030")]:
        sub = t[(t.entry >= f"{a}-01-01") & (t.entry <= f"{b}-12-31")]
        rows.append(dict(period=name, **summarize(sub)))
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    print("\n=== 3) 가장 깊이 물린 거래 TOP 5 (기준 파라미터) ===")
    print(t.sort_values("mae").head(5).assign(
        ret=lambda x: (x.ret * 100).round(1), mae=lambda x: (x.mae * 100).round(1)
    ).to_string(index=False))

    print("\n=== 4) 매수선만 바꿨을 때 (매도 40 고정) ===")
    rows = []
    for b1, b2 in [(33.5, 29.5), (35, 31), (32, 28), (30, 26), (38, 34), (33.5, 25), (33.5, 33.5)]:
        rows.append(dict(b1=b1, b2=b2, **summarize(run(df, b1, b2, 40))))
    print(pd.DataFrame(rows).round(2).to_string(index=False))
    print("\n저장: tqqq_robustness.png")


if __name__ == "__main__":
    main()
