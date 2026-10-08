#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H1-c / H1-g の「1306 を上回る確率」をブロックブートストラップで出す（事後分析）

- 戦略と 1306 の日次リターンの差（超過リターン）を、循環ブロックブートストラップ（ブロック長 20 営業日、
  10,000 回、乱数 seed 0）で再抽出し、期間全体の累積超過が正になる割合を出す
- 1306 側は期末一括課税の前の評価額（税は最終日にだけ効く）、戦略側は税引後の評価額で、2.3 節と同じ扱い
- 3 期間をつないだ系列（2015-01〜2025-12、期間の境目はそのまま連結）でも出す

使い方: python scripts/run/bootstrap_h1.py
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_h1g_dividend_nocut import GRID, load_universe_merged  # noqa: E402
from scripts.run.run_rules_research import CAPITAL, MIN_TURNOVER, PERIODS, build  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.backtest.stats import block_bootstrap_outperform  # noqa: E402
from src.data.benchmark import load_benchmark  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

SPECS = {"H1-c 配当利回り 上位20 毎月": dict(cls="factor", factors=["div_yield"], n=20), **GRID}


def active_series(res) -> pd.Series:
    s = res["history"]["total_value"].pct_change()
    b = res["benchmark"].history["total_value"].reindex(s.index).pct_change()
    return (s - b).dropna()


def main():
    BacktestLogger().setup_logger(log_level="ERROR")
    etf = load_benchmark("1306", str(PROJECT_ROOT / "data" / "cache" / "benchmark"))
    rows, pooled = [], {k: [] for k in SPECS}
    for period, (start, end, data_dir) in PERIODS.items():
        data = load_universe_merged(str(PROJECT_ROOT / data_dir))
        excluded = excluded_codes(data)
        panel = MarketPanel(data)
        cand = Candidates(panel, min_turnover=MIN_TURNOVER, excluded=excluded)
        for name, spec in SPECS.items():
            cfg = RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                              execution=ExecutionConfig())
            res = RulesEngine(cfg, build(spec, cand, name), panel, etf).run()
            a = active_series(res)
            pooled[name].append(a)
            b = block_bootstrap_outperform(a, block_len=20, n_boot=10_000, seed=0)
            rows.append({"期間": period, "条件": name, "1306比": round(res["metrics"]["excess_vs_benchmark"]),
                         "T": b["T"], "超過年率": round(b["mean_ann"], 4), "90%区間下": round(b["mean_lo"], 4),
                         "90%区間上": round(b["mean_hi"], 4), "P(1306超)": round(b["p_outperform"], 3)})
            print(rows[-1], flush=True)
    for name, parts in pooled.items():
        a = pd.concat(parts)
        b = block_bootstrap_outperform(a, block_len=20, n_boot=10_000, seed=0)
        rows.append({"期間": "2015-25 連結", "条件": name, "1306比": None, "T": b["T"], "超過年率": round(b["mean_ann"], 4),
                     "90%区間下": round(b["mean_lo"], 4), "90%区間上": round(b["mean_hi"], 4),
                     "P(1306超)": round(b["p_outperform"], 3)})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    out = PROJECT_ROOT / "data" / "results" / "rules_research" / "bootstrap_h1.tsv"
    df.to_csv(out, sep="\t", index=False)
    pd.set_option("display.width", 250)
    print("\n" + df.to_string(index=False))
    print(f"\n保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
