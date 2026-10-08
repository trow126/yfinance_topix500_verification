#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H1-g 配当利回り × 減配回避（docs/research/hypotheses.md 3b 章、2026-10-08 追加登録）の検証

- 3 条件（毎月 / 四半期 / 半年）× 3 期間
- ランダム比較: 各条件と同じ候補（減配なし）・同じ頻度・同じ銘柄数でランダムに選ぶ（seed 0〜19）
- DSR: H1 グリッドの 7 条件（data/results/rules_research/rules_20261008_202614.tsv）と今回の 3 条件を合わせた
  N = 10 で割り引く

使い方: python scripts/run/run_h1g_dividend_nocut.py --seeds 20
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_rules_research import MIN_TURNOVER, PERIODS, run_one  # noqa: E402
from src.backtest.stats import deflated_sharpe_ratio, random_rank  # noqa: E402
from src.data.benchmark import load_benchmark  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel, load_universe  # noqa: E402
from src.strategy.rules import Candidates  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

PRIOR_H1 = PROJECT_ROOT / "data" / "results" / "rules_research" / "rules_20261008_202614.tsv"


def load_universe_merged(data_dir: str) -> dict:
    """
    減配判定には 2 年分の配当履歴が要るので、2019 年以降の期間では universe（2018-01〜）の前に
    universe_2013（2013-01〜2018-12）を継ぎ足す。重なる 2018 年は universe 側を使う。
    2 つのキャッシュは同じ時期に取得した分割調整済みデータで、重なり期間の終値・配当は一致する（事前確認済み）。
    """
    data = load_universe(data_dir)
    if not data_dir.endswith("universe"):
        return data
    old = load_universe(str(Path(data_dir).parent / "universe_2013"))
    merged = {}
    for code, df in data.items():
        prev = old.get(code)
        if prev is not None:
            prev = prev[prev.index < df.index[0]]
            df = pd.concat([prev, df]) if len(prev) else df
        merged[code] = df
    return merged

GRID = {
    "H1-g1 配当利回り 減配なし 上位20 毎月": dict(cls="factor", factors=["div_yield"], n=20, no_cut=True),
    "H1-g2 配当利回り 減配なし 上位20 四半期": dict(cls="factor", factors=["div_yield"], n=20, no_cut=True, rebalance="Q"),
    "H1-g3 配当利回り 減配なし 上位20 半年": dict(cls="factor", factors=["div_yield"], n=20, no_cut=True, rebalance="H"),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--periods", default="2015-18,2019-22,2023-25")
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")
    etf = load_benchmark("1306", str(PROJECT_ROOT / "data" / "cache" / "benchmark"))
    out_dir = PROJECT_ROOT / "data" / "results" / "rules_research"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for period in args.periods.split(","):
        start, end, data_dir = PERIODS[period]
        data = load_universe_merged(str(PROJECT_ROOT / data_dir))
        excluded = excluded_codes(data)
        panel = MarketPanel(data)
        cand = Candidates(panel, min_turnover=MIN_TURNOVER, excluded=excluded)
        print(f"=== {period}", flush=True)
        for name, spec in GRID.items():
            m = run_one(spec, name, period, panel, cand, etf)
            m["grid"] = "H1g"
            rows.append(m)
            print(f"  {name:<40} 税引後 {m['final_value_after_tax']:>13,.0f}  1306 {m['benchmark_final_after_tax']:>13,.0f}"
                  f"  差 {m['excess_vs_benchmark']:>+12,.0f}  DD {m['max_drawdown']:.1%}/{m['benchmark_max_drawdown']:.1%}"
                  f"  売買 {m['stock_trades']}", flush=True)
            for seed in range(args.seeds):
                r = run_one(spec, f"比較: {name} ランダム#{seed}", period, panel, cand, etf, seed=seed, pick="random")
                r["grid"] = "H1g"
                r["base"] = name
                rows.append(r)
            print(f"  比較: {name} ランダム × {args.seeds}", flush=True)
        pd.DataFrame(rows).to_csv(out_dir / f"h1g_{stamp}.tsv", sep="\t", index=False)

    df = pd.DataFrame(rows)
    prior = pd.read_csv(PRIOR_H1, sep="\t")
    prior = prior[(prior["grid"] == "H1") & ~prior["条件"].str.startswith("比較: ")]
    summary = []
    for period, g in df.groupby("期間"):
        tried = g[~g["条件"].str.startswith("比較: ")]
        all_sr = tried["daily_sr"].tolist() + prior[prior["期間"] == period]["daily_sr"].tolist()
        for _, r in tried.iterrows():
            rnd = g[g.get("base", pd.Series(index=g.index, dtype=object)) == r["条件"]]
            d = deflated_sharpe_ratio(r["daily_sr"], all_sr, int(r["T"]), r["skew"], r["kurt"])
            rk = random_rank(r["excess_vs_benchmark"], rnd["excess_vs_benchmark"].tolist()) if len(rnd) else {}
            summary.append({"期間": period, "条件": r["条件"], "税引後最終": round(r["final_value_after_tax"]),
                            "1306税引後": round(r["benchmark_final_after_tax"]), "1306比": round(r["excess_vs_benchmark"]),
                            "超え": r["excess_vs_benchmark"] > 0, "最大DD": round(r["max_drawdown"], 3),
                            "1306DD": round(r["benchmark_max_drawdown"], 3),
                            "DD悪化pt": round((r["max_drawdown"] - r["benchmark_max_drawdown"]) * 100, 1),
                            "売買回数": r["stock_trades"], "年間回転": round(r["turnover_per_year"], 2), "税": round(r["tax_paid"]),
                            "配当税引後": round(r["dividends_after_tax"]), "日次SR": round(r["daily_sr"], 4),
                            "DSR(N=10)": round(d["dsr"], 3), "SR*": round(d["sr_star"], 4),
                            "ランダム中の位置": round(rk.get("percentile", float("nan")), 2),
                            "ランダム中央値": round(rk.get("median", float("nan"))) if rk else None,
                            "ランダム上位10%": round(rk.get("p90", float("nan"))) if rk else None,
                            "ランダム最大": round(max(rnd["excess_vs_benchmark"])) if len(rnd) else None})
    s = pd.DataFrame(summary)
    s.to_csv(out_dir / f"h1g_summary_{stamp}.tsv", sep="\t", index=False)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    print("\n" + s.to_string())
    print(f"\n保存: {out_dir / f'h1g_summary_{stamp}.tsv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
