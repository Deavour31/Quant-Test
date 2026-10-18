"""닷컴 구간(2000-03~2002-12) QQQ(나스닥100) 3x 레버리지 토큰 매매일지

신호: 합성 TQQQ(나스닥100 x3) 일봉 RSI(14). 1차 <=33.5, 2차 <=29.5 (각 증거금 50%), 매도 >=40.
거래대상: 나스닥100 지수(QQQ 대용), 포지션 단위 3x, 격리마진, 유지증거금 1%, 펀딩비 0 가정.
체결: 신호일 종가. 청산은 일중 저가가 청산가에 닿으면 발생.
"""

import pandas as pd

from tqqq_levtoken import MM, B1, B2, EX, build

L = 3
START, END = "2000-03-01", "2002-12-31"


def log_trades(df: pd.DataFrame) -> pd.DataFrame:
    o, lo, c, rsi, idx = df["Open"].values, df["Low"].values, df["Close"].values, df["rsi"].values, df.index
    rows, pos = [], None

    def add(p, price, m, i):
        u = L * m / price
        p["M"] += m; p["u"] += u; p["N"] += u * price

    for i in range(len(df)):
        if pos is None:
            if rsi[i] <= B1:
                pos = dict(M=0.0, u=0.0, N=0.0, i0=i, t1=(idx[i], c[i], rsi[i]), t2=None, low=c[i])
                add(pos, c[i], 0.5, i)
                if rsi[i] <= B2:
                    add(pos, c[i], 0.5, i); pos["t2"] = (idx[i], c[i], rsi[i])
            continue
        a = pos["N"] / pos["u"]
        p_liq = a * (1 - 1 / L) / (1 - MM)
        pos["low"] = min(pos["low"], lo[i])
        if lo[i] <= p_liq:
            fill = min(p_liq, o[i])
            pnl = max(pos["u"] * (fill - a), -pos["M"])
            rows.append(finish(pos, idx[i], fill, a, p_liq, pnl, i, "청산"))
            pos = None
            continue
        if pos["t2"] is None and rsi[i] <= B2:
            add(pos, c[i], 0.5, i); pos["t2"] = (idx[i], c[i], rsi[i])
            a = pos["N"] / pos["u"]
            p_liq = a * (1 - 1 / L) / (1 - MM)
        if rsi[i] >= EX:
            pnl = pos["u"] * (c[i] - a)
            rows.append(finish(pos, idx[i], c[i], a, p_liq, pnl, i, "RSI≥40 매도"))
            pos = None
    return pd.DataFrame(rows)


def finish(pos, exit_d, exit_p, avg, p_liq, pnl, i, why):
    t1, t2 = pos["t1"], pos["t2"]
    return dict(
        매수1=f"{t1[0]:%Y-%m-%d}", 매수1가=round(t1[1]), RSI1=round(t1[2], 1),
        매수2=(f"{t2[0]:%Y-%m-%d}" if t2 else "-"), 매수2가=(round(t2[1]) if t2 else None),
        평단=round(avg), 청산가=round(p_liq), 최저가=round(pos["low"]),
        최대하락_평단대비=f"{pos['low'] / avg - 1:.1%}",
        매도일=f"{exit_d:%Y-%m-%d}", 매도가=round(exit_p), 사유=why,
        보유일=i - pos["i0"], 지수수익=f"{exit_p / avg - 1:+.1%}",
        증거금=pos["M"], pnl=pnl,
        증거금수익=f"{pnl / pos['M']:+.1%}", 자본손익=f"{pnl * 100:+.1f}%",
    )


def main() -> None:
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    _, stress = build()
    t = log_trades(stress)
    t = t[(t.매수1 >= START) & (t.매수1 <= END)].reset_index(drop=True)
    t.insert(0, "#", t.index + 1)
    eq, curve = 1.0, []
    for p in t.pnl:
        eq *= 1 + p
        curve.append(round(eq, 3))
    t["누적자산"] = curve
    out = t.drop(columns=["증거금", "pnl"])
    print(out.to_string(index=False))
    print(f"\n거래 {len(t)}건 / 수익 {(t.pnl > 0).sum()} / 손실 {(t.pnl <= 0).sum()} / "
          f"청산 {(out.사유 == '청산').sum()} / 최종 자산 {eq:.2f}배 (시작 1.00, 매 거래 자본 100%를 증거금 한도로 운용 가정)")
    with open("dotcom_3x_log.md", "w") as f:
        f.write("# 닷컴 구간 QQQ 3x 매매일지 (나스닥100 지수 기준, 2000-03 ~ 2002-12)\n\n")
        cols = list(out.columns)
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("|" + "---|" * len(cols) + "\n")
        for _, r in out.iterrows():
            f.write("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |\n")
    out.to_csv("dotcom_3x_log.csv", index=False)


if __name__ == "__main__":
    main()
