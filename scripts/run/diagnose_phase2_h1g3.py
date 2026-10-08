#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事後の点検（hypotheses.md 7 章 2026-10-09）: 第 1 期の H1-g3（実績配当利回り・減配なし・半年）を
当日終値約定（第 1 期）と翌営業日終値約定（第 2 期）で回し、H10 の 2019-22 の負けが約定の遅れか財務フィルタかを分ける。
条件の追加ではない（合否判定に使わない）。
"""
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_oos_2026 import load_all, load_etf  # noqa: E402
from scripts.run.run_phase2 import EXPLORE, config  # noqa: E402
from src.backtest.rules_engine import RulesEngine  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates, FactorStrategy  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402


def main():
    BacktestLogger().setup_logger(log_level="ERROR")
    data = load_all()
    etf = load_etf()
    panel = MarketPanel(data)
    cand = Candidates(panel, min_turnover=1_000_000_000, excluded=excluded_codes(data))
    rows = []
    for period, (start, end) in EXPLORE.items():
        for delay in (0, 1):
            s = FactorStrategy(cand, name="H1-g3", factors=["div_yield"], n=20, keep_rank=40, rebalance="H", no_cut=True)
            m = RulesEngine(replace(config(start, end), exec_delay=delay), s, panel, etf).run()["metrics"]
            rows.append({"期間": period, "exec_delay": delay, "1306比": round(m["excess_vs_benchmark"]),
                         "最大DD": round(m["max_drawdown"], 3), "売買": m["stock_trades"]})
            print(rows[-1], flush=True)
    out = PROJECT_ROOT / "data" / "results" / "phase2" / "diagnose_h1g3_delay.tsv"
    pd.DataFrame(rows).to_csv(out, sep="\t", index=False)
    print(f"保存: {out}")


if __name__ == "__main__":
    main()
