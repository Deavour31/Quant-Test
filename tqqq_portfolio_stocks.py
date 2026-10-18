"""본체를 개별 종목 2개(50:50 단순보유)로 바꿨을 때 70% 본체 + 30% 전략 포트폴리오

본체 A: 현재 시총 1·2위 (NVDA, AAPL) -- 사후 선택 편향(과거에 많이 오른 종목)이 있음
본체 B: 2017-01 시작 시점 1·2위 근사 (AAPL, GOOGL) -- 시작 시점에 고를 수 있었던 조합(시총은 근사값)
기준: QQQ 100%. 보조 전략/계산 방식은 tqqq_portfolio.py와 동일(비중 고정, 재조정 없음).
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder
from tqqq_chart import START, simulate
from tqqq_portfolio import W_CORE, W_SLEEVE, stats, top_drawdowns


def px(t: str) -> pd.Series:
    return yf.download(t, start=START, auto_adjust=True, progress=False)["Close"].squeeze().dropna()


def main() -> None:
    pd.set_option("display.width", 220)
    tq = px("TQQQ")
    rsi = rsi_wilder(tq)
    ok = rsi.notna()
    tq, rsi = tq[ok], rsi[ok]
    _, sleeve = simulate(tq, rsi)

    def norm(t):
        s = px(t).reindex(tq.index).ffill()
        return s / s.iloc[0]

    qqq = norm("QQQ")
    cores = {
        "A: NVDA+AAPL 50:50 (현재 1·2위)": 0.5 * norm("NVDA") + 0.5 * norm("AAPL"),
        "B: AAPL+GOOGL 50:50 (2017 시점 1·2위 근사)": 0.5 * norm("AAPL") + 0.5 * norm("GOOGL"),
    }
    print(f"데이터: {tq.index[0].date()} ~ {tq.index[-1].date()}  |  본체-전략 일수익률 상관:")
    for name, core in cores.items():
        print(f"  {name}: {core.pct_change().corr(sleeve.pct_change()):.3f}")

    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex=True, constrained_layout=True)
    for k, (name, core) in enumerate(cores.items()):
        port = W_CORE * core + W_SLEEVE * sleeve
        cash = W_CORE * core + W_SLEEVE
        print(f"\n===== 본체 {name} =====")
        rows = []
        for label, eq in (("본체 100%", core), ("70% 본체 + 30% 전략", port), ("70% 본체 + 30% 현금", cash),
                          ("(참고) QQQ 100%", qqq)):
            t, cg, md = stats(eq)
            rows.append(dict(포트폴리오=label, 총배수=round(t, 2), 연환산=f"{cg:.1f}%", 최대낙폭=f"{md:.1f}%"))
        print(pd.DataFrame(rows).to_string(index=False))

        print("\n--- 본체 주요 하락 구간에서 보조 30%가 메운 정도 (고점 시점 포트폴리오 대비 %) ---")
        rows = []
        for pk, tr, depth in top_drawdowns(core, k=5):
            base = port.loc[pk]
            loss = W_CORE * (core.loc[tr] - core.loc[pk]) / base
            s0 = W_SLEEVE * (sleeve.loc[tr] - sleeve.loc[pk]) / base
            j = min(port.index.get_loc(tr) + 10, len(port) - 1)
            s10 = W_SLEEVE * (sleeve.iloc[j] - sleeve.loc[pk]) / base
            rows.append(dict(구간=f"{pk:%Y-%m-%d}~{tr:%Y-%m-%d}", 본체낙폭=f"{depth * 100:.0f}%",
                             본체손실=f"{loss * 100:+.1f}%", 보조손익_저점=f"{s0 * 100:+.1f}%",
                             메운비율_저점=f"{-s0 / loss * 100:.0f}%", 보조손익_10일뒤=f"{s10 * 100:+.1f}%",
                             메운비율_10일뒤=f"{-s10 / loss * 100:.0f}%"))
        print(pd.DataFrame(rows).to_string(index=False))

        ax = axes[0][k]
        ax.plot(core.index, core, color="gray", lw=1.1, label="100% core")
        ax.plot(port.index, port, color="#d73027", lw=1.4, label="70% core + 30% strategy")
        ax.plot(cash.index, cash, color="#4575b4", lw=1.0, ls="--", label="70% core + 30% cash")
        ax.set_yscale("log"); ax.set_title(f"Core {name.split(':')[0]}: " + name.split(": ")[1].split(" (")[0])
        ax.legend(); ax.grid(alpha=0.3)
        ax = axes[1][k]
        for lab, eq, col in (("100% core", core, "gray"), ("70/30 strategy", port, "#d73027"), ("70/30 cash", cash, "#4575b4")):
            ax.plot(eq.index, (eq / eq.cummax() - 1) * 100, color=col, lw=1.0, label=lab)
        ax.set_ylabel("Drawdown %"); ax.legend(loc="lower left"); ax.grid(alpha=0.3)
    fig.savefig("tqqq_portfolio_stocks.png", dpi=120)
    print("\n저장: tqqq_portfolio_stocks.png")


if __name__ == "__main__":
    main()
