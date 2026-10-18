"""본체가 횡보하는 경우: 삼성전자(005930.KS) 70% + 이 전략 30% (2017-01 ~ END, 기본 2024-12-31)

전략은 원화 현금으로 TQQQ를 사고 원화로 평가한다(환율 반영, 대기 중 현금은 KRW). 신호는 TQQQ(USD) RSI.
비중 고정(재조정 없음), 현금 이자 0%. 비교: 본체 100% / 70%+현금 30% / 70%+전략 30%.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from tqqq_backtest import rsi_wilder
from tqqq_chart import START, simulate
from tqqq_portfolio import W_CORE, W_SLEEVE, stats, top_drawdowns

END = sys.argv[1] if len(sys.argv) > 1 else "2024-12-31"   # 예: python tqqq_portfolio_samsung.py 2026-12-31
OUT = "tqqq_portfolio_samsung.png" if END == "2024-12-31" else f"tqqq_portfolio_samsung_{END[:4]}.png"


def px(t: str) -> pd.Series:
    return yf.download(t, start=START, auto_adjust=True, progress=False)["Close"].squeeze().dropna()


def main() -> None:
    pd.set_option("display.width", 220)
    tq = px("TQQQ")
    rsi = rsi_wilder(tq)
    ok = rsi.notna()
    tq, rsi = tq[ok], rsi[ok]
    idx = tq.index[tq.index <= END]

    fx = px("KRW=X").reindex(tq.index).ffill().bfill()
    if fx.median() < 1:      # USD당 원이 아니라 원당 달러로 내려오면 뒤집는다
        fx = 1 / fx
    ss = px("005930.KS").reindex(tq.index).ffill().bfill()

    _, sleeve_usd = simulate(tq, rsi)                    # 환율 무시(USD 기준)
    _, sleeve_krw = simulate(tq * fx, rsi)               # KRW 현금으로 매수·KRW 평가(환율 반영)
    sleeve_usd, sleeve_krw = (s.loc[idx] / s.loc[idx].iloc[0] for s in (sleeve_usd, sleeve_krw))
    core = (ss / ss.iloc[0]).loc[idx]
    core = core / core.iloc[0]

    print(f"기간 {idx[0].date()} ~ {idx[-1].date()} | 삼성전자 {ss.loc[idx].iloc[0]:,.0f} → {ss.loc[idx].iloc[-1]:,.0f}원(조정가) "
          f"| 원/달러 {fx.loc[idx].iloc[0]:,.0f} → {fx.loc[idx].iloc[-1]:,.0f}")
    print(f"본체-전략(KRW) 일수익률 상관 {core.pct_change().corr(sleeve_krw.pct_change()):.3f}")

    rows = []
    cash = W_CORE * core + W_SLEEVE
    ports = {"본체 100% (삼성전자)": core, "70% + 현금 30%": cash,
             "70% + 전략 30% (환율 무시, USD)": W_CORE * core + W_SLEEVE * sleeve_usd,
             "70% + 전략 30% (환율 반영, KRW)": W_CORE * core + W_SLEEVE * sleeve_krw}
    for label, eq in ports.items():
        t, cg, md = stats(eq)
        rows.append(dict(포트폴리오=label, 총배수=round(t, 2), 연환산=f"{cg:.1f}%", 최대낙폭=f"{md:.1f}%"))
    t, cg, md = stats(sleeve_krw)
    rows.append(dict(포트폴리오="(참고) 전략 단독 100% (KRW)", 총배수=round(t, 2), 연환산=f"{cg:.1f}%", 최대낙폭=f"{md:.1f}%"))
    print(pd.DataFrame(rows).to_string(index=False))

    port = ports["70% + 전략 30% (환율 반영, KRW)"]
    print("\n--- 삼성전자 주요 하락 구간에서 보조 30%(KRW)가 메운 정도 (고점 시점 포트폴리오 대비 %) ---")
    rows = []
    for pk, tr, depth in top_drawdowns(core, k=5):
        base = port.loc[pk]
        loss = W_CORE * (core.loc[tr] - core.loc[pk]) / base
        s0 = W_SLEEVE * (sleeve_krw.loc[tr] - sleeve_krw.loc[pk]) / base
        j = min(port.index.get_loc(tr) + 10, len(port) - 1)
        s10 = W_SLEEVE * (sleeve_krw.iloc[j] - sleeve_krw.loc[pk]) / base
        rows.append(dict(구간=f"{pk:%Y-%m-%d}~{tr:%Y-%m-%d}", 본체낙폭=f"{depth * 100:.0f}%",
                         본체손실=f"{loss * 100:+.1f}%", 보조손익_저점=f"{s0 * 100:+.1f}%",
                         메운비율_저점=f"{-s0 / loss * 100:.0f}%", 보조손익_10일뒤=f"{s10 * 100:+.1f}%",
                         메운비율_10일뒤=f"{-s10 / loss * 100:.0f}%"))
    print(pd.DataFrame(rows).to_string(index=False))

    fig, ax = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True,
                           gridspec_kw=dict(height_ratios=[1.6, 2, 1.6]))
    ax[0].plot(core.index, ss.loc[idx], color="#1f77b4", lw=1.1)
    ax[0].set_ylabel("Samsung Elec. (KRW, adj.)"); ax[0].set_title("Core = Samsung Electronics (sideways), sleeve = 30% RSI split-buy strategy")
    ax[0].grid(alpha=0.3)
    ax[1].plot(core.index, core, color="gray", lw=1.1, label="100% Samsung")
    ax[1].plot(cash.index, cash, color="#4575b4", lw=1.1, ls="--", label="70% Samsung + 30% cash")
    ax[1].plot(port.index, port, color="#d73027", lw=1.5, label="70% Samsung + 30% strategy (KRW)")
    ax[1].set_ylabel("Growth of 1"); ax[1].legend(); ax[1].grid(alpha=0.3)
    for lab, eq, col in (("100% Samsung", core, "gray"), ("70/30 cash", cash, "#4575b4"), ("70/30 strategy", port, "#d73027")):
        ax[2].plot(eq.index, (eq / eq.cummax() - 1) * 100, color=col, lw=1.0, label=lab)
    ax[2].set_ylabel("Drawdown %"); ax[2].legend(loc="lower left"); ax[2].grid(alpha=0.3)
    fig.savefig(OUT, dpi=120)
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
