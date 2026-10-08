#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未使用期間（2026-01-05〜取得できた最終日）で H1-c / H1-g1〜g3 を 1 回だけ確認する

- 価格: universe_2013（2013〜2018）+ universe（2018〜2025）+ universe_2026（2025-06〜2026-10）をつなぐ
- 1306: benchmark（〜2025-12）+ benchmark_2026
- ルール・コスト・税は事前登録と同じ。期間が 9 か月なので「期末に全部売ったとみなす」課税の影響が大きい点に注意

使い方: python scripts/run/run_oos_2026.py [--seeds 20]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_h1g_dividend_nocut import GRID, load_universe_merged  # noqa: E402
from scripts.run.run_rules_research import CAPITAL, MIN_TURNOVER, build  # noqa: E402
from src.backtest.benchmark import buy_and_hold  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.backtest.stats import block_bootstrap_outperform, random_rank  # noqa: E402
from src.data.benchmark import apply_corrections  # noqa: E402
from src.data.quality import excluded_codes, fix_transient_scale_errors  # noqa: E402
from src.strategy.monthly_rights import MarketPanel, load_universe  # noqa: E402
from src.strategy.rules import Candidates  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

SPECS = {"H1-c 配当利回り 上位20 毎月": dict(cls="factor", factors=["div_yield"], n=20), **GRID}


def load_all() -> dict:
    data = load_universe_merged(str(PROJECT_ROOT / "data" / "cache" / "universe"))
    new = load_universe(str(PROJECT_ROOT / "data" / "cache" / "universe_2026"))
    out = {}
    for code, df in data.items():
        add = new.get(code)
        if add is not None:
            add = add[add.index > df.index[-1]]
            if len(add):
                df = pd.concat([df, add])
        out[code] = df
    return out


def load_etf() -> pd.DataFrame:
    old = pd.read_pickle(PROJECT_ROOT / "data" / "cache" / "benchmark" / "1306.pkl")
    new = pd.read_pickle(PROJECT_ROOT / "data" / "cache" / "benchmark_2026" / "1306.pkl")
    new = new[new.index > old.index[-1]]
    # 2026-03-30・31 の終値が 1/10 で記録されている（分割ではなく 2 日で戻る）ので直す
    return fix_transient_scale_errors(apply_corrections(pd.concat([old, new]), "1306"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--start", default="2026-01-05")
    args = p.parse_args()
    BacktestLogger().setup_logger(log_level="ERROR")
    data = load_all()
    etf = load_etf()
    last = max(df.index[-1] for df in data.values())
    end = str(min(last, etf.index[-1]).date())
    print(f"期間 {args.start} 〜 {end}、銘柄 {len(data)}", flush=True)
    excluded = excluded_codes(data)
    panel = MarketPanel(data)
    cand = Candidates(panel, min_turnover=MIN_TURNOVER, excluded=excluded)
    bench = buy_and_hold(etf, args.start, end, CAPITAL)
    print(f"1306 税引後 {bench.final_value_after_tax:,.0f}（損益 {bench.final_value_after_tax - CAPITAL:+,.0f}、DD {bench.max_drawdown:.1%}）", flush=True)
    rows = []
    for name, spec in SPECS.items():
        cfg = RulesConfig(start_date=args.start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                          execution=ExecutionConfig())
        res = RulesEngine(cfg, build(spec, cand, name), panel, etf).run()
        m = res["metrics"]
        s = res["history"]["total_value"].pct_change()
        b = res["benchmark"].history["total_value"].reindex(s.index).pct_change()
        bb = block_bootstrap_outperform((s - b).dropna(), block_len=20, n_boot=10_000)
        rnd = []
        for seed in range(args.seeds):
            r = RulesEngine(cfg, build(spec, cand, f"rnd{seed}", seed=seed, pick="random"), panel, etf).run()
            rnd.append(r["metrics"]["excess_vs_benchmark"])
        rk = random_rank(m["excess_vs_benchmark"], rnd)
        rows.append({"条件": name, "税引後最終": round(m["final_value_after_tax"]), "1306比": round(m["excess_vs_benchmark"]),
                     "最大DD": round(m["max_drawdown"], 3), "1306DD": round(m["benchmark_max_drawdown"], 3),
                     "売買": m["stock_trades"], "税": round(m["tax_paid"]), "P(1306超)": round(bb["p_outperform"], 3),
                     "ランダム中の位置": round(rk["percentile"], 2), "ランダム中央値": round(rk["median"]), "ランダム上位10%": round(rk["p90"])})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    out = PROJECT_ROOT / "data" / "results" / "rules_research" / "oos_2026.tsv"
    df.to_csv(out, sep="\t", index=False)
    pd.set_option("display.width", 250)
    print("\n" + df.to_string(index=False))
    print(f"\n保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
