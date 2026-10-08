#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 2 期の検証（docs/research/hypotheses.md 3d〜3h 章）を 1 仮説ずつ回す

- 約定は判断日の翌営業日の終値（exec_delay=1）。H8R-b/c だけ判断日の始値
- 判定は src/backtest/evaluation.py（売らない版、上位 3 件除外、コスト感度、ランダム比較、超過 PSR・ブートストラップ・DSR）
- 価格は universe_2013 + universe + universe_2026 をつないだもの（run_oos_2026.load_all）、1306 は補正つき（load_etf）
- 確認期間は、登録どおり探索 2 期間の両方で 1306 を上回った条件だけを回す（--confirm を付けたときだけ。1 回だけ）

使い方:
    python scripts/run/run_phase2.py --hyp H9 --seeds 20
    python scripts/run/run_phase2.py --hyp H9 --seeds 20 --confirm
    python scripts/run/run_phase2.py --hyp H8R --seeds 20
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_h8_large_holdings import load_events  # noqa: E402
from scripts.run.run_oos_2026 import load_all, load_etf  # noqa: E402
from src.backtest.evaluation import COST_LEVELS, cost_key, evaluate, verdict  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates, EventHold, YearEndLosers  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

CAPITAL = 15_000_000
EXPLORE = {"2015-18": ("2015-01-05", "2018-12-28"), "2019-22": ("2019-01-04", "2022-12-30")}
CONFIRM = {"2023-25": ("2023-01-04", "2025-12-30"), "2026": ("2026-01-05", "2026-10-08")}
H8R_PERIODS = {"2021-23": ("2021-12-01", "2023-12-29"), "2024-26": ("2024-01-04", "2026-10-08")}
OUT = PROJECT_ROOT / "data" / "results" / "phase2"


# ---------------------------------------------------------------------- 提出者の分類（3f 章、この順で判定）
FINANCIAL = re.compile(r"証券|銀行|保険|フィナンシャル|Securities|Bank", re.I)
FUND = re.compile(r"弁護士|法律事務所|キャピタル|アセット|マネジメント|インベストメント|パートナーズ|ファンド|アドバイザ|投資|"
                  r"Capital|Management|Investment|Partners|Fund|Advisor|LLC|L\.P\.|Limited|Ltd|PTE", re.I)
COMPANY = re.compile(r"株式会社|有限会社|合同会社|合資会社|社団法人|財団法人|Inc|Corporation", re.I)


def classify_filer(name: str) -> str:
    name = str(name)
    if FINANCIAL.search(name):
        return "金融機関"
    if FUND.search(name):
        return "ファンド"
    if COMPANY.search(name):
        return "事業会社"
    return "個人"


def config(start, end, exec_delay=1, exec_price="close") -> RulesConfig:
    return RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                       exec_delay=exec_delay, exec_price=exec_price, execution=ExecutionConfig())


def summarize(rows, name):
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT / f"{name}_{stamp}.tsv"
    df.to_csv(path, sep="\t", index=False)
    cols = ["条件", "期間", "excess", "excess_no_sell", "excess_ex_top3", *[cost_key(c) for c in COST_LEVELS],
            "max_dd", "bench_dd", "stock_trades", "random_trades_median", "random_percentile", "psr", "p_boot",
            "dsr_active", "median_ret", "win_rate", "max_participation", "max_trades_month"]
    pd.set_option("display.width", 400)
    pd.set_option("display.max_columns", 60)
    print("\n" + df[[c for c in cols if c in df]].to_string(index=False), flush=True)
    vcols = [c for c in df.columns if c[:1].isdigit() and "_" in c]
    print("\n" + df[["条件", "期間", *vcols]].to_string(index=False), flush=True)
    print(f"\n保存: {path}", flush=True)
    return df


def record(rows, name, period, out):
    row = {"条件": name, "期間": period, **out["row"]}
    row.update(verdict(out["row"]))
    rows.append(row)
    short = {k: (round(v) if isinstance(v, float) and abs(v) > 100 else (round(v, 3) if isinstance(v, float) else v))
             for k, v in row.items() if k in ("条件", "期間", "excess", "excess_no_sell", "excess_ex_top3", "psr", "p_boot",
                                               "random_percentile", "stock_trades", cost_key(0.002))}
    print(short, flush=True)


# ---------------------------------------------------------------------- H9
def run_h9(panel, etf, cand, seeds, confirm):
    name = "H9-a 年末3営業日前に年初来上位20 1月末に売る"

    def factory(seed, pick):
        return YearEndLosers(cand, name=name, n=20, entry_days_before=3, pick=pick or "top", seed=seed)

    rows = []
    periods = dict(EXPLORE)
    if confirm:
        periods = {"2023-25": CONFIRM["2023-25"], "2026": ("2025-12-01", "2026-10-08")}
    for period, (start, end) in periods.items():
        print(f"=== {period}", flush=True)
        record(rows, name, period, evaluate(factory, config(start, end), panel, etf, seeds=seeds, n_trials=6))
    return summarize(rows, "h9_confirm" if confirm else "h9")


# ---------------------------------------------------------------------- H8R
H8R_GRID = {
    "H8R-a 活動家×ファンド/事業会社 1億 60日 翌営業日終値": dict(filers=("ファンド", "事業会社"), exec_delay=1, exec_price="close"),
    "H8R-b 活動家×ファンド/事業会社 1億 60日 始値": dict(filers=("ファンド", "事業会社"), exec_delay=0, exec_price="open"),
    "H8R-c 活動家(全提出者) 1億 60日 始値": dict(filers=None, exec_delay=0, exec_price="open"),
}


def h8r_events():
    ev = load_events()
    ev = ev[ev["activist"]].copy()
    ev["filer_class"] = ev["filer_name"].map(classify_filer)
    return ev


def run_h8r(panel, etf, excluded, seeds):
    ev_all = h8r_events()
    print(f"活動家目的イベント {len(ev_all)} 件、提出者の分類: {ev_all['filer_class'].value_counts().to_dict()}", flush=True)
    cand = Candidates(panel, min_turnover=100_000_000, excluded=excluded)
    rows = []
    for period, (start, end) in H8R_PERIODS.items():
        print(f"=== {period}", flush=True)
        for name, spec in H8R_GRID.items():
            ev = ev_all if spec["filers"] is None else ev_all[ev_all["filer_class"].isin(spec["filers"])]
            ev = ev[(ev["date"] >= start) & (ev["date"] <= end)][["date", "code"]]

            def factory(seed, pick, ev=ev, name=name):
                return EventHold(cand, ev, name=name, hold_days=60, max_positions=10, entry_lag=1,
                                 pick=pick or "event", seed=seed)

            out = evaluate(factory, config(start, end, spec["exec_delay"], spec["exec_price"]), panel, etf,
                           seeds=seeds, n_trials=7)
            out["row"]["events"] = len(ev)
            record(rows, name, period, out)
    df = summarize(rows, "h8r")
    strata = h8r_strata(ev_all, panel, etf)
    path = OUT / f"h8r_strata_{datetime.now():%Y%m%d_%H%M%S}.tsv"
    strata.to_csv(path, sep="\t", index=False)
    print("\n層別（事後の診断。提出の 2 営業日後の終値 → 60 営業日後の終値、1306 との差）\n" + strata.to_string(index=False))
    print(f"保存: {path}")
    return df


def h8r_strata(ev, panel, etf):
    cal = panel.calendar
    etf_close = etf["Close"].reindex(cal).ffill()
    close = panel.close_ffill
    rows = []
    for _, e in ev.iterrows():
        i = cal.searchsorted(e["date"], side="right") + 1  # 提出の 2 営業日後
        j = i + 60
        if j >= len(cal) or e["code"] not in close.columns:
            continue
        p0, p1 = close.iloc[i][e["code"]], close.iloc[j][e["code"]]
        if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        r = p1 / p0 - 1 - (etf_close.iloc[j] / etf_close.iloc[i] - 1)
        ratio = pd.to_numeric(e["holding_ratio"], errors="coerce")
        bin_ = "不明" if pd.isna(ratio) else ("5〜7.5%" if ratio < 0.075 else ("7.5〜10%" if ratio < 0.10 else "10%以上"))
        rows.append({"filer_class": e["filer_class"], "ratio_bin": bin_, "excess": r, "year": e["date"].year})
    d = pd.DataFrame(rows)
    out = []
    for keys, g in list(d.groupby(["filer_class", "ratio_bin"])) + [(("全体", "全体"), d)]:
        x = g["excess"]
        out.append({"提出者": keys[0], "保有割合": keys[1], "件数": len(x), "平均": round(x.mean(), 4),
                    "中央値": round(x.median(), 4), "勝率": round((x > 0).mean(), 3),
                    "上位3除く平均": round(x.sort_values().iloc[:-3].mean(), 4) if len(x) > 3 else np.nan})
    return pd.DataFrame(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hyp", required=True, choices=["H9", "H8R"])
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--confirm", action="store_true", help="確認期間を回す（探索で基準 1 を満たした条件だけ。1 回だけ）")
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")
    data = load_all()
    etf = load_etf()
    excluded = excluded_codes(data)
    panel = MarketPanel(data)
    print(f"銘柄 {len(data)}、異常値で除外 {len(excluded)}、営業日 {panel.calendar[0].date()}〜{panel.calendar[-1].date()}", flush=True)
    if args.hyp == "H9":
        run_h9(panel, etf, Candidates(panel, min_turnover=1_000_000_000, excluded=excluded), args.seeds, args.confirm)
    else:
        run_h8r(panel, etf, excluded, args.seeds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
