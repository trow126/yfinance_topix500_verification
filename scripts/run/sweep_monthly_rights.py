#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略（みんかぶランキング版）の条件を変えて比較する

過去の結果に合わせ込みすぎないよう、期間を2つに分けて同じ条件で回す:
- 前半（条件を比べる期間）: 2019-10 〜 2022-12
- 後半（確かめる期間）    : 2023-01 〜 2025-12
前半で良かった条件が後半でも良いかを見る。

使い方:
    python scripts/run/sweep_monthly_rights.py [--config config/monthly_rights_minkabu_config.yaml] [--seeds 20]
"""

import argparse
import copy
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.monthly_rights_engine import MonthlyRightsEngine  # noqa: E402
from src.strategy.monthly_rights import MarketPanel, MonthlyRightsConfig, load_universe  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402

PERIODS = {"前半": ("2019-10-01", "2022-12-31"), "後半": ("2023-01-01", "2025-12-31")}

# 名前 → 基本設定からの変更点（"区分.項目": 値）
ROUND1 = {
    # 6. 比較対象
    "基本（上位3）": {},
    "比較: 下位3": {"selection.pick": "bottom"},
    "比較: 客観指標": {"selection.source": "objective"},
    # 1. 銘柄数
    "上位5": {"selection.top_n": 5},
    "上位10": {"selection.top_n": 10},
    # 2. 出口
    "最長1年": {"trading.max_holding_days": 365},
    "最長半年": {"trading.max_holding_days": 182},
    "ナンピン後-15%損切り": {"trading.stop_loss_pct": 0.15},
    "最長1年+損切り": {"trading.max_holding_days": 365, "trading.stop_loss_pct": 0.15},
    # 3. 購入タイミング
    "5営業日前に購入": {"trading.entry_days_before_ex": 5},
    "10営業日前に購入": {"trading.entry_days_before_ex": 10},
    "15営業日前に購入": {"trading.entry_days_before_ex": 15},
    # 4. 継続保有が条件の優待
    "継続保有条件を除外": {"selection.exclude_continuous_holding": True},
    # 5. ナンピン
    "ナンピンなし": {"trading.nanpin_max": 0},
    "ナンピン1回": {"trading.nanpin_max": 1},
    "ナンピン3回": {"trading.nanpin_max": 3},
    "ナンピン-5%刻み": {"trading.nanpin_step": 0.05},
    "ナンピン-15%刻み": {"trading.nanpin_step": 0.15},
    "ナンピン-20%刻み": {"trading.nanpin_step": 0.20},
}


def round2() -> dict:
    """選び方 × ナンピン上限 × 最長保有期間"""
    bases = {
        "人気上位3": {},
        "人気→利回り順3": {"selection.rank_by": "dividend_yield"},
        "人気(代金1億↑)→利回り順3": {"selection.rank_by": "dividend_yield",
                                  "selection.ranking_min_turnover": 100_000_000},
        "客観3": {"selection.source": "objective"},
        "客観5": {"selection.source": "objective", "selection.top_n": 5},
    }
    variants = {}
    for base_name, base in bases.items():
        for nanpin in (2, 5, 9):  # -10%刻みなので9回で-90%まで（実質無制限）
            for hold, hold_name in ((0, ""), (365, "+最長1年")):
                variants[f"{base_name} ナンピン{nanpin}{hold_name}"] = {
                    **base, "trading.nanpin_max": nanpin, "trading.max_holding_days": hold}
    return variants


# 2014〜2017年の利回りランキング版（config/monthly_rights_minkabu_2014_config.yaml: ナンピン5・最長1年が基本）
# 客観指標は全銘柄ではなく、株価を取得したランキング掲載銘柄の中からしか選べない点に注意
OLD = {
    "利回り上位3": {},
    "比較: 利回り下位3": {"selection.pick": "bottom"},
    "利回り上位3 ナンピン2": {"trading.nanpin_max": 2},
    "利回り上位3 期限なし": {"trading.max_holding_days": 0},
    "利回り上位5": {"selection.top_n": 5},
    "客観3（取得銘柄内）": {"selection.source": "objective"},
    "客観5（取得銘柄内）": {"selection.source": "objective", "selection.top_n": 5},
}

def objective() -> dict:
    """客観指標版（売買代金10億円/日以上・その月に権利がある銘柄を実績配当利回り順）"""
    base = {"selection.source": "objective"}
    variants = {}
    for n in (3, 5):
        for nanpin in (2, 5):
            for hold, hold_name in ((0, ""), (365, "+最長1年")):
                variants[f"客観{n} ナンピン{nanpin}{hold_name}"] = {
                    **base, "selection.top_n": n, "trading.nanpin_max": nanpin,
                    "trading.max_holding_days": hold}
    variants["比較: 客観の下位5（利回りが低い順）ナンピン5+最長1年"] = {
        **base, "selection.top_n": 5, "selection.pick": "bottom",
        "trading.nanpin_max": 5, "trading.max_holding_days": 365}
    return variants


# ランダム比較の対象（--grid objective のときは客観指標の候補からランダムに5銘柄）
RANDOM_BASE = {
    "objective": {"selection.source": "objective", "selection.top_n": 5,
                  "trading.nanpin_max": 5, "trading.max_holding_days": 365},
}

GRIDS = {"round1": lambda: ROUND1, "round2": round2, "old": lambda: OLD, "objective": objective}

COLUMNS = {
    "profit": "損益(円)", "return_on_invested": "投資額比/年", "total_return": "口座リターン",
    "max_drawdown": "最大DD", "cycles": "回数", "win_rate_closed": "勝率", "open_cycles": "保有中",
    "worst_open_pnl": "最大含み損", "median_holding_days_closed": "保有中央値(日)",
    "max_holding_days": "最長保有(日)", "avg_invested": "平均投資額", "max_invested": "最大投資額",
    "skipped_for_cash": "資金不足",
}


def apply(config: MonthlyRightsConfig, changes: dict) -> MonthlyRightsConfig:
    config = copy.deepcopy(config)
    for key, value in changes.items():
        section, name = key.split(".")
        setattr(getattr(config, section), name, value)
    return config


def run(base, panel, data, name, changes, period):
    config = apply(base, changes)
    config.start_date, config.end_date = PERIODS[period]
    if config.selection.source == "objective":
        # 客観指標版は人気の代わりに売買代金と利回りで選ぶ。月の途中の優待日は扱わない
        config.selection.min_turnover = 1_000_000_000
    m = MonthlyRightsEngine(config, data, panel).run()["metrics"]
    return {"条件": name, "期間": period, **{label: m[key] for key, label in COLUMNS.items()},
            "出口": m["exit_reasons"]}


def main():
    parser = argparse.ArgumentParser(description="月次権利取り戦略の条件比較")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "monthly_rights_minkabu_config.yaml"))
    parser.add_argument("--seeds", type=int, default=20, help="ランダム選定の試行回数")
    parser.add_argument("--grid", choices=list(GRIDS), default="round2")
    parser.add_argument("--periods", default=None,
                        help="期間を変える（例: 2015-01-01:2016-12-31,2017-01-01:2018-12-31 → 前半・後半）")
    args = parser.parse_args()
    variants = GRIDS[args.grid]()
    if args.periods:
        spans = [p.split(":") for p in args.periods.split(",")]
        PERIODS.clear()
        PERIODS.update(dict(zip(["前半", "後半"], [tuple(s) for s in spans])))

    BacktestLogger().setup_logger(log_level="ERROR")
    base = MonthlyRightsConfig.from_yaml(args.config)
    base.data_dir = str(PROJECT_ROOT / base.data_dir)
    for attr in ("ranking_file", "benefits_file"):
        path = getattr(base.selection, attr)
        if path:
            setattr(base.selection, attr, str(PROJECT_ROOT / path))

    print("データ読み込み中...", flush=True)
    data = load_universe(base.data_dir)
    panel = MarketPanel(data, base.selection.turnover_window)

    rows = []
    for name, changes in variants.items():
        for period in PERIODS:
            rows.append(run(base, panel, data, name, changes, period))
        print(f"  {name}", flush=True)
    for seed in range(args.seeds):
        for period in PERIODS:
            rows.append(run(base, panel, data, f"比較: ランダム#{seed}",
                            {**RANDOM_BASE.get(args.grid, {}), "selection.pick": "random",
                             "selection.random_seed": seed}, period))
    print(f"  比較: ランダム × {args.seeds}", flush=True)

    df = pd.DataFrame(rows)
    out = PROJECT_ROOT / "data" / "results" / "monthly_rights_sweep"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"sweep_{datetime.now():%Y%m%d_%H%M%S}.tsv"
    df.to_csv(path, sep="\t", index=False)

    # 表示: ランダムは分布（中央値と上下10%）にまとめる
    random_rows = df[df["条件"].str.startswith("比較: ランダム")]
    summary = (random_rows.groupby("期間")[["損益(円)", "投資額比/年", "勝率"]]
               .quantile([0.1, 0.5, 0.9]).unstack(level=1))
    main_rows = df[~df["条件"].str.startswith("比較: ランダム")]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for period in PERIODS:
        t = main_rows[main_rows["期間"] == period].drop(columns=["期間", "出口"]).set_index("条件")
        t["損益(円)"] = t["損益(円)"].round(-3).astype(int)
        t["最大含み損"] = t["最大含み損"].round(-3).astype(int)
        for col in ("平均投資額", "最大投資額"):
            t[col] = (t[col] / 10_000).round().astype(int).astype(str) + "万"
        for c in ("投資額比/年", "口座リターン", "最大DD", "勝率"):
            t[c] = (t[c] * 100).round(1).astype(str) + "%"
        print(f"\n===== {period} {PERIODS[period][0]} 〜 {PERIODS[period][1]} =====")
        print(t.to_string())
        s = summary.loc[period]
        print(f"  ランダム{args.seeds}回: 損益 中央値 {s[('損益(円)', 0.5)]:,.0f} 円"
              f"（下位10% {s[('損益(円)', 0.1)]:,.0f} 〜 上位10% {s[('損益(円)', 0.9)]:,.0f}）、"
              f"投資額比/年 中央値 {s[('投資額比/年', 0.5)]:.1%}")
    print(f"\n保存しました: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
