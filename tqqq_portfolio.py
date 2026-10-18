"""70% 본체(단순보유) + 30% 이 전략(보조 자금) 포트폴리오: 본체 하락을 얼마나 메우는가

본체 가정: QQQ 단순보유 또는 TQQQ 단순보유. 보조: tqqq_chart.simulate(기준 전략, TQQQ 현물), 자본 100% 운용·
평가손익 포함·현금 이자 0%. 비중은 시작 시점 70/30 고정(재조정 없음). 실제 TQQQ 일봉 2017-01~현재.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder
from tqqq_chart import START, simulate

W_CORE, W_SLEEVE = 0.7, 0.3


def top_drawdowns(s: pd.Series, k: int = 4, min_depth: float = 0.15):
    """신고점 사이의 낙폭 구간(에피소드)별 (고점일, 저점일, 깊이) 중 깊은 순 k개. 구간은 서로 겹치지 않는다."""
    eps, peak_d, peak_v, trough_d, trough_v = [], s.index[0], s.iloc[0], s.index[0], s.iloc[0]
    for d, v in s.items():
        if v >= peak_v:
            if trough_v / peak_v - 1 <= -min_depth:
                eps.append((peak_d, trough_d, trough_v / peak_v - 1))
            peak_d, peak_v, trough_d, trough_v = d, v, d, v
        elif v < trough_v:
            trough_d, trough_v = d, v
    if trough_v / peak_v - 1 <= -min_depth:
        eps.append((peak_d, trough_d, trough_v / peak_v - 1))
    return sorted(eps, key=lambda e: e[2])[:k]


def stats(eq: pd.Series):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    tot = eq.iloc[-1] / eq.iloc[0]
    return tot, (tot ** (1 / yrs) - 1) * 100, (eq / eq.cummax() - 1).min() * 100


def main() -> None:
    tq = yf.download("TQQQ", start=START, auto_adjust=True, progress=False)["Close"].squeeze().dropna()
    qq = yf.download("QQQ", start=START, auto_adjust=True, progress=False)["Close"].squeeze().dropna()
    rsi = rsi_wilder(tq)
    ok = rsi.notna()
    tq, rsi = tq[ok], rsi[ok]
    _, sleeve = simulate(tq, rsi)
    qq = qq.reindex(tq.index).ffill()
    cores = {"QQQ": qq / qq.iloc[0], "TQQQ": tq / tq.iloc[0]}

    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True, constrained_layout=True)
    for name, core in cores.items():
        port = W_CORE * core + W_SLEEVE * sleeve
        print(f"\n===== 본체 = {name} 단순보유 | 포트폴리오 = 70% 본체 + 30% 전략 =====")
        rows = []
        for label, eq in ((f"{name} 100% 단순보유", core), ("70/30 포트폴리오", port),
                          (f"70% {name} + 30% 현금(전략 없음)", W_CORE * core + W_SLEEVE)):
            t, cg, md = stats(eq)
            rows.append(dict(포트폴리오=label, 총배수=round(t, 2), 연환산=f"{cg:.1f}%", 최대낙폭=f"{md:.1f}%"))
        print(pd.DataFrame(rows).to_string(index=False))

        print(f"\n--- 본체 주요 하락 구간(고점→저점)에서 보조 30%가 메운 정도 (고점 시점 포트폴리오 가치 대비 %) ---")
        rows = []
        for pk, tr, depth in top_drawdowns(core):
            base = port.loc[pk]
            core_loss = W_CORE * (core.loc[tr] - core.loc[pk]) / base    # 본체 70%의 손실(고점 시점 포트폴리오 대비)
            sl_chg = W_SLEEVE * (sleeve.loc[tr] - sleeve.loc[pk]) / base # 보조 30%의 변화
            j = min(port.index.get_loc(tr) + 10, len(port) - 1)           # 저점 10거래일 뒤(반등 직후 청산분 포함)
            sl10 = W_SLEEVE * (sleeve.iloc[j] - sleeve.loc[pk]) / base
            rows.append(dict(구간=f"{pk:%Y-%m-%d}~{tr:%Y-%m-%d}", 본체낙폭=f"{depth * 100:.0f}%",
                             본체손실=f"{core_loss * 100:+.1f}%",
                             보조손익_저점=f"{sl_chg * 100:+.1f}%",
                             메운비율_저점=f"{-sl_chg / core_loss * 100:.0f}%",
                             보조손익_저점10일뒤=f"{sl10 * 100:+.1f}%",
                             메운비율_10일뒤=f"{-sl10 / core_loss * 100:.0f}%"))
        print(pd.DataFrame(rows).to_string(index=False))

        if name == "QQQ":
            axes[0].plot(core.index, core, color="gray", lw=1.1, label="100% QQQ buy & hold")
            axes[0].plot(port.index, port, color="#d73027", lw=1.4, label="70% QQQ + 30% strategy")
            axes[0].plot(port.index, W_CORE * core + W_SLEEVE, color="#4575b4", lw=1.0, ls="--",
                         label="70% QQQ + 30% cash")
            axes[0].set_yscale("log"); axes[0].set_ylabel("Growth of 1 (log)"); axes[0].legend(); axes[0].grid(alpha=0.3)
            for lab, eq, col in (("100% QQQ", core, "gray"), ("70% QQQ + 30% strategy", port, "#d73027"),
                                 ("70% QQQ + 30% cash", W_CORE * core + W_SLEEVE, "#4575b4")):
                axes[1].plot(eq.index, (eq / eq.cummax() - 1) * 100, color=col, lw=1.0, label=lab)
            axes[1].set_ylabel("Drawdown %"); axes[1].legend(loc="lower left"); axes[1].grid(alpha=0.3)
    axes[0].set_title("Core QQQ buy&hold + 30% RSI split-buy strategy sleeve (real data, 2017~)")
    fig.savefig("tqqq_portfolio.png", dpi=120)
    print("\n저장: tqqq_portfolio.png")


if __name__ == "__main__":
    main()
