#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略のバックテストを実行する

事前に全銘柄データを取得しておくこと:
    python scripts/data/fetch_universe_data.py

使い方:
    python scripts/run/run_monthly_rights_backtest.py [--config config/monthly_rights_config.yaml]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.monthly_rights_engine import MonthlyRightsEngine, save_results  # noqa: E402
from src.strategy.monthly_rights import MonthlyRightsConfig, load_universe  # noqa: E402
from src.utils.logger import BacktestLogger  # noqa: E402


def load_names() -> dict:
    path = PROJECT_ROOT / "config" / "universe" / "jp_stock_codes.txt"
    names = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            code, name, *_ = line.split("\t")
            names[code] = name
    return names


def print_summary(results: dict) -> None:
    m = results["metrics"]
    names = load_names()
    print("\n" + "=" * 64)
    print("【月次権利取り戦略 バックテスト結果】")
    print("=" * 64)
    print(f"  初期資本        : {m['initial_capital']:>14,.0f} 円")
    print(f"  最終評価額      : {m['final_value']:>14,.0f} 円")
    print(f"  総リターン      : {m['total_return']:>14.2%}")
    print(f"  年率リターン    : {m['cagr']:>14.2%}")
    print(f"  最大ドローダウン: {m['max_drawdown']:>14.2%}")
    print(f"  受取配当(税引後): {m['total_dividend_after_tax']:>14,.0f} 円")
    print(f"  手数料合計      : {m['total_commission']:>14,.0f} 円")
    print(f"  平均投資額      : {m['avg_invested']:>14,.0f} 円（最大 {m['max_invested']:,.0f} 円）")
    print("\n■ サイクル（1銘柄の購入〜売却）")
    print(f"  合計 {m['cycles']} 件 / 売却済み {m['closed_cycles']} 件 / 保有中 {m['open_cycles']} 件")
    print(f"  売却済みの勝率  : {m['win_rate_closed']:.1%}")
    print(f"  実現損益        : {m['realized_pnl']:>14,.0f} 円（配当込み）")
    print(f"  保有中の含み損益: {m['unrealized_pnl_open']:>14,.0f} 円")
    print(f"  保有日数        : 平均 {m['avg_holding_days_closed']:.0f} 日 / "
          f"中央値 {m['median_holding_days_closed']:.0f} 日 / 最長 {m['max_holding_days']} 日")
    print(f"  ナンピン回数    : {m['nanpin_trades']}")
    print(f"  資金不足で見送り: {m['skipped_for_cash']} 件")

    positions = results["positions"]
    if not positions.empty:
        p = positions.copy()
        p["year"] = pd.to_datetime(p["entry_date"]).dt.year
        p["month"] = pd.to_datetime(p["entry_date"]).dt.month
        p["pnl"] = p["realized_pnl"].where(p["status"] == "CLOSED", p["unrealized_pnl"] + p["dividend_received"])
        print("\n■ 購入年別（保有中は含み損益+受取配当）")
        print(p.groupby("year").agg(件数=("pnl", "size"), 損益=("pnl", "sum"),
                                    保有中=("status", lambda s: (s == "OPEN").sum())).round(0).to_string())

        opened = p[p["status"] == "OPEN"].sort_values("unrealized_pnl")
        if not opened.empty:
            print("\n■ 保有中（取得単価まで戻っていない）")
            for r in opened.itertuples():
                print(f"  {r.ticker} {names.get(r.ticker, ''):<12} 購入 {r.entry_date}  "
                      f"含み損益 {r.unrealized_pnl:>10,.0f} 円  配当 {r.dividend_received:>8,.0f} 円")

    sel = results["selections"]
    if not sel.empty and "rights_date_source" in sel:
        labels = {"edinet": "有報の優待基準日", "dividend": "同月の配当の権利落ち日", "assumed": "月末と仮定"}
        print("\n■ 優待の権利確定日の決め方")
        for source, n in sel["rights_date_source"].value_counts().items():
            print(f"  {labels.get(source, source)}: {n} 件")
        if "continuous_holding" in sel:
            n = int((sel["continuous_holding"] == "required").sum())
            print(f"  うち継続保有が条件の優待（初回は優待をもらえない可能性）: {n} 件")
            n = int((sel["edinet_benefit"] == False).sum())  # noqa: E712
            print(f"  うち有報に優待の記載がない: {n} 件")
    excluded = results.get("excluded")
    if excluded is not None and not excluded.empty:
        reason = excluded["reason"].str.replace(r"（.*）", "", regex=True)
        print("\n■ ランキング上位から外した理由（件数）")
        print(reason.value_counts().to_string())
        missing = excluded[excluded["reason"] == "株価データなし"]
        if not missing.empty:
            print("  株価データなし: " + ", ".join(
                f"{c} {n}" for c, n in missing.drop_duplicates("code")[["code", "name"]].values[:20]))
    if not sel.empty:
        if "name" not in sel:
            sel = sel.assign(name=sel["code"].map(names))
        sel = sel.assign(month=sel["selection_date"].dt.month)
        print("\n■ 選ばれた回数の多い銘柄")
        top = sel.groupby(["code", "name"]).size().sort_values(ascending=False).head(15)
        print(top.to_string())
        print("\n■ 月別の選定銘柄数（全期間合計）")
        print(sel.groupby("month").size().to_string())
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(description="月次権利取り戦略のバックテスト")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "monthly_rights_config.yaml"))
    args = parser.parse_args()

    BacktestLogger().setup_logger(log_level="WARNING")
    config = MonthlyRightsConfig.from_yaml(args.config)

    print(f"データ読み込み中: {config.data_dir}")
    data = load_universe(str(PROJECT_ROOT / config.data_dir))
    if not data:
        print("データがありません。先に scripts/data/fetch_universe_data.py を実行してください")
        return 1
    print(f"  {len(data)} 銘柄")

    engine = MonthlyRightsEngine(config, data)
    print(f"バックテスト実行中: {config.start_date} 〜 {config.end_date}")
    results = engine.run()
    print_summary(results)
    out = save_results(results, str(PROJECT_ROOT / config.results_dir))
    print(f"\n結果を保存しました: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
