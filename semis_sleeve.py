"""삼성전자 본체(70%) + 보조 30%: 신호를 나스닥(TQQQ) vs 반도체(SOXL) vs 반반으로 바꿔 비교

SOXL 전략 = 기준 전략(RSI(14) 33.5/29.5 분할매수, 40 매도, 손절 없음)을 SOXL 자체 RSI로 SOXL에 적용.
보조 자금은 원화 현금으로 매수·원화 평가(환율 반영). 비중 고정, 현금 이자 0%.
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


def build_sleeve(ticker: str, fx: pd.Series):
    p = px(ticker)
    r = rsi_wilder(p)
    ok = r.notna()
    p, r = p[ok], r[ok]
    trades, eq = simulate(p * fx.reindex(p.index).ffill().bfill(), r)
    return trades, eq


def main() -> None:
    pd.set_option("display.width", 220)
    fx = px("KRW=X")
    if fx.median() < 1:
        fx = 1 / fx
    tr_t, sl_t = build_sleeve("TQQQ", fx)
    tr_s, sl_s = build_sleeve("SOXL", fx)

    print("=== 전략 단독 성적 (USD 기준 거래 통계, 2017~) ===")
    rows = []
    for name, t in (("TQQQ 신호/TQQQ", tr_t), ("SOXL 신호/SOXL", tr_s)):
        rows.append(dict(전략=name, 거래수=len(t), 수익확률=f"{(t.ret > 0).mean() * 100:.1f}%",
                         평균수익=f"{t.ret.mean() * 100:.1f}%", 평균보유=round(t.hold.mean(), 1),
                         최악거래=f"{t.ret.min() * 100:.1f}%", 최악보유중낙폭=f"{t.worst.min() * 100:.1f}%"))
    print(pd.DataFrame(rows).to_string(index=False))

    idx = sl_t.index.intersection(sl_s.index)
    ss = px("005930.KS").reindex(idx).ffill().bfill()
    core_full = ss / ss.iloc[0]
    sleeves = {"TQQQ 신호": sl_t.reindex(idx), "SOXL 신호": sl_s.reindex(idx)}
    sleeves = {k: v / v.iloc[0] for k, v in sleeves.items()}
    sleeves["50:50 혼합"] = 0.5 * sleeves["TQQQ 신호"] + 0.5 * sleeves["SOXL 신호"]

    for end in ("2024-12-31", "2026-12-31"):
        sel = idx[idx <= end]
        core = core_full.loc[sel] / core_full.loc[sel].iloc[0]
        print(f"\n===== 삼성전자 본체, {sel[0].date()} ~ {sel[-1].date()} =====")
        rows = []
        cands = {"삼성전자 100%": core, "70% + 현금 30%": W_CORE * core + W_SLEEVE}
        for name, sl in sleeves.items():
            s = sl.loc[sel] / sl.loc[sel].iloc[0]
            cands[f"70% + 전략 30% ({name})"] = W_CORE * core + W_SLEEVE * s
        for label, eq in cands.items():
            t, cg, md = stats(eq)
            rows.append(dict(포트폴리오=label, 총배수=round(t, 2), 연환산=f"{cg:.1f}%", 최대낙폭=f"{md:.1f}%"))
        print(pd.DataFrame(rows).to_string(index=False))

    print("\n===== 삼성전자 주요 하락 구간에서 보조 30%가 메운 정도 (저점 10일 뒤, 고점 시점 포트폴리오 대비) =====")
    core = core_full
    eps = top_drawdowns(core, k=5)
    rows = []
    for pk, tr, depth in eps:
        row = dict(구간=f"{pk:%Y-%m-%d}~{tr:%Y-%m-%d}", 본체낙폭=f"{depth * 100:.0f}%")
        for name, sl in sleeves.items():
            port = W_CORE * core + W_SLEEVE * sl
            base = port.loc[pk]
            loss = W_CORE * (core.loc[tr] - core.loc[pk]) / base
            j = min(port.index.get_loc(tr) + 10, len(port) - 1)
            s10 = W_SLEEVE * (sl.iloc[j] - sl.loc[pk]) / base
            row[f"{name} 메운비율"] = f"{-s10 / loss * 100:.0f}%"
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

    fig, ax = plt.subplots(2, 1, figsize=(16, 10), sharex=True, constrained_layout=True)
    styles = {"TQQQ 신호": "#d73027", "SOXL 신호": "#1a9850", "50:50 혼합": "#984ea3"}
    en = {"TQQQ 신호": "TQQQ signal", "SOXL 신호": "SOXL signal", "50:50 혼합": "50:50 mix"}
    ax[0].plot(core.index, core, color="gray", lw=1.1, label="100% Samsung")
    ax[0].plot(core.index, W_CORE * core + W_SLEEVE, color="#4575b4", lw=1.0, ls="--", label="70% + 30% cash")
    ax[1].plot(core.index, (core / core.cummax() - 1) * 100, color="gray", lw=1.0, label="100% Samsung")
    for name, sl in sleeves.items():
        port = W_CORE * core + W_SLEEVE * sl
        ax[0].plot(port.index, port, color=styles[name], lw=1.3, label=f"70% + 30% strategy ({en[name]})")
        ax[1].plot(port.index, (port / port.cummax() - 1) * 100, color=styles[name], lw=1.0, label=en[name])
    ax[0].set_ylabel("Growth of 1"); ax[0].legend(); ax[0].grid(alpha=0.3)
    ax[0].set_title("Core Samsung Electronics + 30% strategy sleeve: Nasdaq (TQQQ) vs semis (SOXL) signal")
    ax[1].set_ylabel("Drawdown %"); ax[1].legend(loc="lower left"); ax[1].grid(alpha=0.3)
    fig.savefig("semis_sleeve.png", dpi=120)
    print("\n저장: semis_sleeve.png")


if __name__ == "__main__":
    main()
