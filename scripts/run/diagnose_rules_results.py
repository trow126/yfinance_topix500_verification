#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事前登録した検証（run_rules_research.py）の結果を点検する（条件は増やさない）

1. H1 / H5 の各条件を再実行して日次の評価額を保存し、1306 に対する超過リターンの
   日次シャープレシオと Deflated Sharpe Ratio を出す（事後の追加分析。報告にはそう書く）
2. 損益が大きい取引を並べ、保有中の 1 日の最大下落と分割の記録を照らし合わせて、
   データ異常（分割未記録など）が結果を作っていないか確かめる
3. 配当利回り戦略（H1-c）が受け取った配当と、選んだ銘柄の利回りの分布を出す

使い方: python scripts/run/diagnose_rules_results.py --periods 2015-18,2019-22,2023-25
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_rules_research import CAPITAL, GRIDS, MIN_TURNOVER, PERIODS, build  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.backtest.stats import deflated_sharpe_ratio, probabilistic_sharpe_ratio  # noqa: E402
from src.data.benchmark import load_benchmark  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel, load_universe  # noqa: E402
from src.strategy.rules import Candidates  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402


def active_stats(history: pd.DataFrame, bench_history: pd.DataFrame) -> dict:
    s = history["total_value"].pct_change().dropna()
    b = bench_history["total_value"].reindex(s.index).pct_change().reindex(s.index)
    a = (s - b).dropna()
    x = a.to_numpy()
    sr = float(a.mean() / a.std()) if a.std() > 0 else 0.0
    m, sd = x.mean(), x.std()
    skew = float(((x - m) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    kurt = float(((x - m) ** 4).mean() / sd ** 4) if sd > 0 else 3.0
    return {"active_sr": sr, "active_skew": skew, "active_kurt": kurt, "T": int(len(a)),
            "active_ann_ret": float(a.mean() * 252), "active_ann_vol": float(a.std() * np.sqrt(252))}


def worst_trades(res, panel, data, n=8):
    closed = res["closed"]
    if closed.empty:
        return pd.DataFrame()
    rows = []
    for _, t in closed.sort_values("pnl").head(n).iterrows():
        code = t["code"]
        px = panel.close_ffill[code].loc[t["entry_date"]:t["exit_date"]]
        r = px.pct_change(fill_method=None)
        worst_day = r.idxmin() if len(r.dropna()) else None
        splits = data[code]["Stock Splits"]
        split_near = splits.loc[t["entry_date"]:t["exit_date"]]
        rows.append({"code": code, "entry": t["entry_date"].date(), "exit": t["exit_date"].date(),
                     "pnl": round(t["pnl"]), "ret": round(t["exit_price"] / t["avg_price"] - 1, 3),
                     "worst_day": worst_day.date() if worst_day is not None else None,
                     "worst_day_ret": round(float(r.min()), 3) if len(r.dropna()) else None,
                     "splits_in_hold": split_near[split_near > 0].to_dict(), "reason": t["reason"]})
    return pd.DataFrame(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--periods", default="2015-18,2019-22,2023-25")
    p.add_argument("--grids", default="H1,H5")
    p.add_argument("--out", default="data/results/rules_research/diagnose")
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")
    etf = load_benchmark("1306", str(PROJECT_ROOT / "data" / "cache" / "benchmark"))
    out = PROJECT_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 60)

    summary = []
    for period in args.periods.split(","):
        start, end, data_dir = PERIODS[period]
        data = load_universe(str(PROJECT_ROOT / data_dir))
        excluded = excluded_codes(data)
        panel = MarketPanel(data)
        cand = Candidates(panel, min_turnover=MIN_TURNOVER, excluded=excluded)
        for gname in args.grids.split(","):
            stats = []
            for name, spec in GRIDS[gname].items():
                if spec["cls"] == "index_tom":
                    continue
                cfg = RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                                  execution=ExecutionConfig())
                res = RulesEngine(cfg, build(spec, cand, name), panel, etf).run()
                a = active_stats(res["history"], res["benchmark"].history)
                a.update({"期間": period, "条件": name, "1306比": round(res["metrics"]["excess_vs_benchmark"]),
                          "配当税引後": round(res["metrics"]["dividends_after_tax"]),
                          "実現損益合計": round(res["closed"]["pnl"].sum()) if len(res["closed"]) else 0})
                stats.append(a)
                with open(out / f"{period}_{gname}_{name[:6]}.pkl", "wb") as f:
                    pickle.dump({"history": res["history"], "closed": res["closed"], "trades": res["trades"],
                                 "bench": res["benchmark"].history}, f)
                if name.startswith(("H1-a", "H1-c", "H5-a", "H5-d")):
                    print(f"\n### {period} {name}: 損失の大きい取引（保有中の最大下落日と分割記録）")
                    print(worst_trades(res, panel, data).to_string(index=False))
                    closed = res["closed"]
                    if len(closed):
                        print(f"  取引 {len(closed)} 件 勝率 {(closed['pnl'] > 0).mean():.2f} "
                              f"損益合計 {closed['pnl'].sum():,.0f} 中央値 {closed['pnl'].median():,.0f} "
                              f"最大 {closed['pnl'].max():,.0f} 最小 {closed['pnl'].min():,.0f}")
                        top = closed.groupby("code")["pnl"].agg(["count", "sum"]).sort_values("sum")
                        print("  損益合計の下位5銘柄:", top.head(5).round(0).to_dict("index"))
                        print("  損益合計の上位5銘柄:", top.tail(5).round(0).to_dict("index"))
                    if name.startswith("H1-c"):
                        picks = res["trades"][res["trades"]["side"] == "BUY"]
                        print(f"  買い {len(picks)} 回、銘柄数 {picks['code'].nunique()}、"
                              f"多い順: {picks['code'].value_counts().head(10).to_dict()}")
            # 超過リターンの DSR（事後分析）
            srs = [s["active_sr"] for s in stats]
            for s in stats:
                d = deflated_sharpe_ratio(s["active_sr"], srs, s["T"], s["active_skew"], s["active_kurt"])
                s["PSR(>0)"] = round(probabilistic_sharpe_ratio(s["active_sr"], 0.0, s["T"], s["active_skew"], s["active_kurt"]), 3)
                s["DSR_active"] = round(d["dsr"], 3)
                s["SR*_active"] = round(d["sr_star"], 4)
                summary.append(s)
    df = pd.DataFrame(summary)
    cols = ["期間", "条件", "1306比", "配当税引後", "実現損益合計", "active_ann_ret", "active_ann_vol", "active_sr",
            "PSR(>0)", "DSR_active", "SR*_active", "T"]
    print("\n### 1306 に対する超過リターンの統計（事後分析）")
    print(df[cols].round(4).to_string(index=False))
    df.to_csv(out / "active_summary.tsv", sep="\t", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
