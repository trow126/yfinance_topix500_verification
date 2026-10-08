#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H8 大量保有報告書（5% ルール）のイベント戦略（docs/research/hypotheses.md 3c 章）の検証

- イベント: data/edinet/large_holdings.tsv（scripts/data/fetch_edinet_large_holdings.py）から
  活動家目的（重要提案・経営参加）の新規 5% 超過報告を抽出
- 4 条件 × 2 期間、各条件にランダム比較 20 本、DSR（N=4）、超過リターンの PSR とブロックブートストラップ

使い方: python scripts/run/run_h8_large_holdings.py --seeds 20
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_oos_2026 import load_all, load_etf  # noqa: E402
from scripts.run.run_rules_research import CAPITAL  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.backtest.stats import (block_bootstrap_outperform, daily_sharpe, deflated_sharpe_ratio,  # noqa: E402
                                probabilistic_sharpe_ratio, random_rank)
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates, EventHold  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

EVENTS_FILE = PROJECT_ROOT / "data" / "edinet" / "large_holdings.tsv"
PERIODS = {"2021-23": ("2021-12-01", "2023-12-29"), "2024-26": ("2024-01-04", "2026-10-08")}
ACTIVIST = re.compile(r"重要提案|経営参加|経営に参加|経営への参加")
NEGATIVE = re.compile(r"行わない|目的としない|目的ではない|予定はない|予定しない")
GRID = {
    "H8-a 活動家目的 代金1億以上 60日": dict(min_turnover=100_000_000, hold_days=60, activist=True),
    "H8-b 活動家目的 代金10億以上 60日": dict(min_turnover=1_000_000_000, hold_days=60, activist=True),
    "H8-c 活動家目的 代金1億以上 120日": dict(min_turnover=100_000_000, hold_days=120, activist=True),
    "比較: 全イベント 代金1億以上 60日": dict(min_turnover=100_000_000, hold_days=60, activist=False),
}


def load_events() -> pd.DataFrame:
    ev = pd.read_csv(EVENTS_FILE, sep="\t", dtype=str).fillna("")
    ev = ev[ev["issuer_code"].str.fullmatch(r"[0-9][0-9A-Z][0-9][0-9A-Z]") & (ev["filing_date"] != "")]
    ev["date"] = pd.to_datetime(ev["filing_date"], errors="coerce")
    ev = ev.dropna(subset=["date"]).rename(columns={"issuer_code": "code"})
    ev["activist"] = ev["purpose"].str.contains(ACTIVIST) & ~ev["purpose"].str.contains(NEGATIVE)
    ev = ev.drop_duplicates(["date", "code"])
    return ev[["date", "code", "activist", "purpose", "holding_ratio", "filer_name"]]


def active_stats(res) -> dict:
    s = res["history"]["total_value"].pct_change()
    b = res["benchmark"].history["total_value"].reindex(s.index).pct_change()
    a = (s - b).dropna()
    x = a.to_numpy()
    sd = x.std()
    sr = float(a.mean() / sd) if sd > 0 else 0.0
    skew = float(((x - x.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    kurt = float(((x - x.mean()) ** 4).mean() / sd ** 4) if sd > 0 else 3.0
    bb = block_bootstrap_outperform(a, block_len=20, n_boot=10_000, seed=0)
    return {"active_sr": sr, "PSR(>0)": round(probabilistic_sharpe_ratio(sr, 0.0, len(a), skew, kurt), 3),
            "P(1306超)": round(bb["p_outperform"], 3), "超過年率": round(bb["mean_ann"], 4)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")
    events = load_events()
    print(f"イベント {len(events)} 件、活動家目的 {int(events['activist'].sum())} 件 "
          f"（{events['date'].min().date()}〜{events['date'].max().date()}）", flush=True)
    for y, g in events.groupby(events["date"].dt.year):
        print(f"  {y}: 全 {len(g)} / 活動家 {int(g['activist'].sum())}", flush=True)
    data = load_all()
    etf = load_etf()
    excluded = excluded_codes(data)
    panel = MarketPanel(data)
    out_dir = PROJECT_ROOT / "data" / "results" / "rules_research"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for period, (start, end) in PERIODS.items():
        print(f"=== {period}", flush=True)
        for name, spec in GRID.items():
            cand = Candidates(panel, min_turnover=spec["min_turnover"], excluded=excluded)
            ev = events[events["activist"]] if spec["activist"] else events
            ev = ev[(ev["date"] >= start) & (ev["date"] <= end)]
            cfg = RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                              execution=ExecutionConfig())
            strat = EventHold(cand, ev[["date", "code"]], name=name, hold_days=spec["hold_days"])
            res = RulesEngine(cfg, strat, panel, etf).run()
            m = res["metrics"]
            sh = daily_sharpe(res["history"]["total_value"])
            a = active_stats(res)
            rnd = []
            for seed in range(args.seeds):
                r = RulesEngine(cfg, EventHold(cand, ev[["date", "code"]], name=f"rnd{seed}", hold_days=spec["hold_days"],
                                               pick="random", seed=seed), panel, etf).run()
                rnd.append(r["metrics"]["excess_vs_benchmark"])
            rk = random_rank(m["excess_vs_benchmark"], rnd)
            closed = res["closed"]
            rows.append({"期間": period, "条件": name, "イベント": len(ev), "買えた": int((res["trades"]["side"] == "BUY").sum()),
                         "候補外": len(strat.skipped), "税引後最終": round(m["final_value_after_tax"]),
                         "1306税引後": round(m["benchmark_final_after_tax"]), "1306比": round(m["excess_vs_benchmark"]),
                         "最大DD": round(m["max_drawdown"], 3), "1306DD": round(m["benchmark_max_drawdown"], 3),
                         "株比率": round(m["avg_stock_exposure"], 2), "勝率": round(m["win_rate"], 2) if len(closed) else None,
                         "1件平均損益": round(closed["pnl"].mean()) if len(closed) else None,
                         "税": round(m["tax_paid"]), "daily_sr": sh["sr"], "skew": sh["skew"], "kurt": sh["kurt"], "T": sh["T"],
                         **a, "ランダム中の位置": round(rk["percentile"], 2), "ランダム中央値": round(rk["median"]),
                         "ランダム上位10%": round(rk["p90"]), "ランダム最大": round(max(rnd))})
            print({k: v for k, v in rows[-1].items() if k not in ("skew", "kurt", "T", "daily_sr")}, flush=True)
    df = pd.DataFrame(rows)
    for period, g in df.groupby("期間"):
        tried = g[~g["条件"].str.startswith("比較: ")]
        srs = g["daily_sr"].tolist()  # N = 4（比較用を含む）
        for i, r in tried.iterrows():
            d = deflated_sharpe_ratio(r["daily_sr"], srs, int(r["T"]), r["skew"], r["kurt"])
            df.loc[i, "DSR(N=4)"] = round(d["dsr"], 3)
    df.to_csv(out_dir / f"h8_summary_{stamp}.tsv", sep="\t", index=False)
    pd.set_option("display.width", 320)
    pd.set_option("display.max_columns", 40)
    cols = ["期間", "条件", "イベント", "買えた", "候補外", "1306比", "最大DD", "1306DD", "株比率", "勝率", "1件平均損益", "税",
            "超過年率", "PSR(>0)", "P(1306超)", "DSR(N=4)", "ランダム中の位置", "ランダム中央値", "ランダム上位10%", "ランダム最大"]
    print("\n" + df[cols].to_string(index=False))
    print(f"\n保存: {out_dir / f'h8_summary_{stamp}.tsv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
