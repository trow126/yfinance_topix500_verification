#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H8-a の点検: 上位取引への依存、保有目的の内訳（重要提案 / 役員・創業者の経営参加）、価格データの確認（事後分析）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.diagnose_rules_results import worst_trades  # noqa: E402
from scripts.run.run_h8_large_holdings import PERIODS, load_events  # noqa: E402
from scripts.run.run_oos_2026 import load_all, load_etf  # noqa: E402
from scripts.run.run_rules_research import CAPITAL  # noqa: E402
from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates, EventHold  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402


def main():
    BacktestLogger().setup_logger(log_level="ERROR")
    events = load_events()
    data = load_all()
    etf = load_etf()
    excluded = excluded_codes(data)
    panel = MarketPanel(data)
    cand = Candidates(panel, min_turnover=100_000_000, excluded=excluded)
    pd.set_option("display.width", 250)
    for period, (start, end) in PERIODS.items():
        ev = events[events["activist"] & (events["date"] >= start) & (events["date"] <= end)]
        cfg = RulesConfig(start_date=start, end_date=end, initial_capital=CAPITAL, sweep_ticker="1306",
                          execution=ExecutionConfig())
        res = RulesEngine(cfg, EventHold(cand, ev[["date", "code"]], name="H8-a", hold_days=60), panel, etf).run()
        c = res["closed"].copy()
        c["ret"] = c["exit_price"] / c["avg_price"] - 1
        s = c.sort_values("pnl", ascending=False)
        print(f"### {period} H8-a: closed {len(c)} mean ret {c['ret'].mean():.3f} median {c['ret'].median():.3f} "
              f"sum pnl {c['pnl'].sum():,.0f}")
        print(s.head(8)[["code", "entry_date", "exit_date", "ret", "pnl"]].to_string(index=False))
        print("  上位3件を除いた損益合計:", round(s.iloc[3:]["pnl"].sum()), " 上位5件除外:", round(s.iloc[5:]["pnl"].sum()),
              " 上位10件除外:", round(s.iloc[10:]["pnl"].sum()))
        ev2 = ev.copy()
        ev2["kind"] = ev2["purpose"].apply(lambda t: "重要提案" if "重要提案" in t else "経営参加")
        kinds = ev2.set_index(["date", "code"])["kind"].to_dict()
        c["kind"] = [kinds.get((pd.Timestamp(d), k), "?") for d, k in zip(c["event_date"], c["code"])]
        print(c.groupby("kind").agg(n=("pnl", "size"), mean_ret=("ret", "mean"), win=("ret", lambda x: (x > 0).mean()),
                                    pnl=("pnl", "sum")).round(3).to_string())
        print("  損失上位")
        print(worst_trades(res, panel, data, 4).to_string(index=False))
        for _, t in s.head(5).iterrows():
            px = panel.close_ffill[t["code"]].loc[t["entry_date"]:t["exit_date"]]
            r = px.pct_change(fill_method=None)
            splits = int(data[t["code"]].loc[t["entry_date"]:t["exit_date"]]["Stock Splits"].gt(0).sum())
            print(f"  {t['code']}: 最大日次 {r.max():+.3f} ({r.idxmax().date()}) 最小日次 {r.min():+.3f} 保有中の分割 {splits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
