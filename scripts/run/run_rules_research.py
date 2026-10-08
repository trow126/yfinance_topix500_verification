#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
インデックス超え調査（docs/research/hypotheses.md）の検証を一括で回す

- 期間: 2015〜2018（universe_2013）/ 2019〜2022 / 2023〜2025（universe）
- 各戦略を 3 期間で回し、1306 全額保有（税引後）と比べる
- 同じ候補からのランダム選定を seeds 回まわして分布を出す
- 試した条件の数で割り引いた Deflated Sharpe Ratio を出す

使い方:
    python scripts/run/run_rules_research.py --grid H1 --seeds 20
    python scripts/run/run_rules_research.py --grid all --periods 2015-18
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.backtest.stats import daily_sharpe, deflated_sharpe_ratio, random_rank  # noqa: E402
from src.data.benchmark import load_benchmark  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel, load_universe  # noqa: E402
from src.strategy.rules import Candidates, FactorStrategy, IndexTiming, PostExRebound, YearEndLosers  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

PERIODS = {
    "2015-18": ("2015-01-05", "2018-12-28", "data/cache/universe_2013"),
    "2019-22": ("2019-01-04", "2022-12-30", "data/cache/universe"),
    "2023-25": ("2023-01-04", "2025-12-30", "data/cache/universe"),
}
CAPITAL = 15_000_000
MIN_TURNOVER = 1_000_000_000

# hypotheses.md に書いた条件（ここに足すときは hypotheses.md にも理由と日付を書く）
GRIDS = {
    "H1": {
        "H1-a モメンタム12-1 上位20 毎月": dict(cls="factor", factors=["mom_12_1"], n=20),
        "H1-b 低ボラ 上位20 毎月": dict(cls="factor", factors=["low_vol"], n=20),
        "H1-c 配当利回り 上位20 毎月": dict(cls="factor", factors=["div_yield"], n=20),
        "H1-d 合成(モメ+低ボラ+利回り) 上位20 毎月": dict(cls="factor", factors=["mom_12_1", "low_vol", "div_yield"], n=20),
        "H1-e 合成 上位20 四半期": dict(cls="factor", factors=["mom_12_1", "low_vol", "div_yield"], n=20, rebalance="Q"),
        "H1-f 合成 上位40 毎月": dict(cls="factor", factors=["mom_12_1", "low_vol", "div_yield"], n=40, keep_rank=80),
        "比較: H1 モメンタム下位20": dict(cls="factor", factors=["mom_12_1"], n=20, pick="bottom"),
    },
    "H5": {
        "H5-a 落ち日買い 利回り順 1日3銘柄 最大15 窓埋め/90日": dict(cls="post_ex", n_per_day=3, max_positions=15, max_days=90),
        "H5-b 落ち日買い 利回り順 1日3銘柄 最大15 窓埋め/180日": dict(cls="post_ex", n_per_day=3, max_positions=15, max_days=180),
        "H5-c 落ち3日後買い 利回り順 1日3銘柄 最大15 窓埋め/90日": dict(cls="post_ex", n_per_day=3, max_positions=15, max_days=90, entry_offset=3),
        "H5-d 落ち日買い 利回り2%以上 1日3銘柄 最大15 窓埋め/90日": dict(cls="post_ex", n_per_day=3, max_positions=15, max_days=90, min_yield=0.02),
    },
    "H6": {
        "H6-a 年末3営業日前に年初来下位20を買い 1月末に売る": dict(cls="year_end", n=20, entry_days_before=3),
        "H6-b 年末5営業日前に年初来下位20を買い 1月末に売る": dict(cls="year_end", n=20, entry_days_before=5),
        "比較: H6 年初来上位20": dict(cls="year_end", n=20, entry_days_before=3, pick="top"),
        "H6-c 1306を月末1日前〜月初3日だけ持つ": dict(cls="index_tom", before=1, after=3),
        "H6-d 1306を月末3日前〜月初3日だけ持つ": dict(cls="index_tom", before=3, after=3),
    },
}
RANDOM_BASE = {  # ランダム比較の土台（同じ売買頻度・銘柄数）
    "H1": dict(cls="factor", factors=["mom_12_1"], n=20),
    "H5": dict(cls="post_ex", n_per_day=3, max_positions=15, max_days=90),
    "H6": dict(cls="year_end", n=20, entry_days_before=3),
}


def build(spec: Dict, cand: Candidates, name: str, seed: int = 0, pick: str = None):
    s = dict(spec)
    cls = s.pop("cls")
    if pick:
        s["pick"] = pick
    if cls == "factor":
        return FactorStrategy(cand, name=name, seed=seed, **s)
    if cls == "post_ex":
        return PostExRebound(cand, name=name, seed=seed, **s)
    if cls == "year_end":
        return YearEndLosers(cand, name=name, seed=seed, **s)
    if cls == "index_tom":
        return IndexTiming(name=name, **s)
    raise ValueError(cls)


def run_one(spec, name, period, panel, cand, etf, seed=0, pick=None) -> Dict:
    start, end, _ = PERIODS[period]
    strategy = build(spec, cand, name, seed, pick)
    is_index = spec["cls"] == "index_tom"
    cfg = RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL,
                      sweep_ticker="" if is_index else "1306", execution=ExecutionConfig())
    res = RulesEngine(cfg, strategy, panel, etf).run()
    m = res["metrics"]
    sh = daily_sharpe(res["history"]["total_value"])
    m.update({"条件": name, "期間": period, "seed": seed, "pick": pick or spec.get("pick", "top"),
              "daily_sr": sh["sr"], "skew": sh["skew"], "kurt": sh["kurt"], "T": sh["T"]})
    if is_index:  # 1306 を株として持つので比較対象は別に出す
        from src.backtest.benchmark import buy_and_hold
        b = buy_and_hold(etf, start, end, CAPITAL)
        m["benchmark_final_after_tax"] = b.final_value_after_tax
        m["excess_vs_benchmark"] = m["final_value_after_tax"] - b.final_value_after_tax
        m["benchmark_max_drawdown"] = b.max_drawdown
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grid", default="all", help="H1 / H5 / H6 / all")
    p.add_argument("--periods", default="2015-18,2019-22,2023-25")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--out", default="data/results/rules_research")
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")

    grids = GRIDS if args.grid == "all" else {args.grid: GRIDS[args.grid]}
    periods = args.periods.split(",")
    etf = load_benchmark("1306", str(PROJECT_ROOT / "data" / "cache" / "benchmark"))
    out_dir = PROJECT_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows = []
    for period in periods:
        start, end, data_dir = PERIODS[period]
        print(f"=== {period}: データ読み込み {data_dir}", flush=True)
        data = load_universe(str(PROJECT_ROOT / data_dir))
        excluded = excluded_codes(data)
        print(f"  {len(data)} 銘柄、異常値で除外 {len(excluded)} 銘柄: {sorted(excluded)}", flush=True)
        panel = MarketPanel(data)
        index_panel = MarketPanel({"1306": etf[etf.index.isin(panel.calendar)]})
        cand = Candidates(panel, min_turnover=MIN_TURNOVER, excluded=excluded)
        for gname, grid in grids.items():
            for name, spec in grid.items():
                pnl = panel if spec["cls"] != "index_tom" else index_panel
                m = run_one(spec, name, period, pnl, cand, etf)
                m["grid"] = gname
                rows.append(m)
                print(f"  {name:<50} 税引後 {m['final_value_after_tax']:>13,.0f}  1306 {m['benchmark_final_after_tax']:>13,.0f}"
                      f"  差 {m['excess_vs_benchmark']:>+12,.0f}  DD {m['max_drawdown']:.1%}/{m['benchmark_max_drawdown']:.1%}"
                      f"  売買 {m['stock_trades']}", flush=True)
            base = RANDOM_BASE.get(gname)
            if base and args.seeds:
                for seed in range(args.seeds):
                    m = run_one(base, f"比較: {gname} ランダム#{seed}", period, panel, cand, etf, seed=seed, pick="random")
                    m["grid"] = gname
                    rows.append(m)
                print(f"  比較: {gname} ランダム × {args.seeds}", flush=True)
        pd.DataFrame(rows).to_csv(out_dir / f"rules_{stamp}.tsv", sep="\t", index=False)

    df = pd.DataFrame(rows)
    # DSR: 同じグリッド・同じ期間で試した条件（ランダムを除く）の日次シャープの分散と個数で割り引く
    summary = []
    for (gname, period), g in df.groupby(["grid", "期間"]):
        tried = g[~g["条件"].str.startswith("比較: ")]
        rnd = g[g["条件"].str.contains("ランダム#")]
        for _, r in tried.iterrows():
            d = deflated_sharpe_ratio(r["daily_sr"], tried["daily_sr"].tolist(), int(r["T"]), r["skew"], r["kurt"])
            rk = random_rank(r["excess_vs_benchmark"], rnd["excess_vs_benchmark"].tolist()) if len(rnd) else {}
            summary.append({"grid": gname, "期間": period, "条件": r["条件"],
                            "税引後最終": round(r["final_value_after_tax"]), "1306税引後": round(r["benchmark_final_after_tax"]),
                            "1306比": round(r["excess_vs_benchmark"]), "超え": r["excess_vs_benchmark"] > 0,
                            "最大DD": round(r["max_drawdown"], 3), "1306DD": round(r["benchmark_max_drawdown"], 3),
                            "DD悪化pt": round((r["max_drawdown"] - r["benchmark_max_drawdown"]) * 100, 1),
                            "売買回数": r["stock_trades"], "年間回転": round(r["turnover_per_year"], 2),
                            "税": round(r["tax_paid"]), "日次SR": round(r["daily_sr"], 4),
                            "DSR": round(d["dsr"], 3), "SR*": round(d["sr_star"], 4), "試行数": d["n_trials"],
                            "ランダム中の位置": round(rk.get("percentile", float("nan")), 2),
                            "ランダム中央値": round(rk.get("median", float("nan"))) if rk else None,
                            "ランダム上位10%": round(rk.get("p90", float("nan"))) if rk else None})
    s = pd.DataFrame(summary)
    s.to_csv(out_dir / f"summary_{stamp}.tsv", sep="\t", index=False)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    print("\n" + s.to_string())
    print(f"\n保存: {out_dir / f'summary_{stamp}.tsv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
