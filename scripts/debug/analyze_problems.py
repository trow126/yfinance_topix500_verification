#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細なポジション分析
問題の原因を特定する
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


def analyze_positions_detail():
    """ポジションの詳細分析"""
    print("=== ポジション詳細分析 ===\n")

    # 最新のポジションファイルを読み込み
    results_dir = Path("data/results")
    position_files = sorted(results_dir.glob("positions_*.csv"))

    if not position_files:
        print("ポジションファイルが見つかりません")
        return

    latest = position_files[-1]
    df = pd.read_csv(latest)

    # 日付をdatetimeに変換
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])

    # 保有期間を計算
    df["holding_days"] = (df["exit_date"] - df["entry_date"]).dt.days

    # 投資額を計算
    df["investment"] = df["entry_price"] * df["total_shares"]

    # リターン率を計算
    df["return_rate"] = df["realized_pnl"] / df["investment"]

    # 各ポジションの詳細を表示
    for idx, row in df.iterrows():
        print(f"\n【ポジション {idx + 1}: {row['ticker']}】")
        print(
            f"エントリー: {row['entry_date'].strftime('%Y-%m-%d')} @ {row['entry_price']:.2f}円"
        )
        print(
            f"決済: {row['exit_date'].strftime('%Y-%m-%d')} @ {row['exit_price']:.2f}円"
        )
        print(f"株数: {row['total_shares']:,}株")
        print(f"保有期間: {row['holding_days']}日")
        print(f"投資額: {row['investment']:,.0f}円")
        print(f"実現損益: {row['realized_pnl']:,.0f}円")
        print(f"リターン率: {row['return_rate']:.2%}")
        print(f"配当受取: {row['dividend_received']:.0f}円")
        print(f"手数料合計: {row['total_commission']:.0f}円")
        print(f"決済理由: {row['exit_reason']}")

        # 年率換算（保有期間1日以上の場合のみ）
        if row["holding_days"] > 0:
            annualized = (1 + row["return_rate"]) ** (365 / row["holding_days"]) - 1
            print(f"年率換算: {annualized:.2%}")


def check_dividend_dates():
    """配当日のチェック"""
    print("\n\n=== 配当日チェック ===\n")

    # バックテスト期間
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)

    print(
        f"バックテスト期間: {start_date.strftime('%Y-%m-%d')} ～ {end_date.strftime('%Y-%m-%d')}"
    )

    # 権利確定日の例（3月と9月）
    record_dates = [datetime(2023, 3, 31), datetime(2023, 9, 30)]

    for record_date in record_dates:
        # 配当支払日を計算
        if record_date.month == 3:
            payment_date = datetime(record_date.year, 6, 25)
        elif record_date.month == 9:
            payment_date = datetime(record_date.year, 12, 10)
        else:
            payment_date = record_date + pd.Timedelta(days=75)

        print(f"\n権利確定日: {record_date.strftime('%Y-%m-%d')}")
        print(f"配当支払日: {payment_date.strftime('%Y-%m-%d')}")

        if payment_date > end_date:
            print("⚠️ 配当支払日がバックテスト期間外です！")
        else:
            print("✓ 配当支払日はバックテスト期間内です")


def analyze_trades():
    """売買記録の分析"""
    print("\n\n=== 売買記録分析 ===\n")

    results_dir = Path("data/results")
    trade_files = sorted(results_dir.glob("trades_*.csv"))

    if not trade_files:
        return

    latest = trade_files[-1]
    trades_df = pd.read_csv(latest)
    trades_df["date"] = pd.to_datetime(trades_df["date"])

    # 銘柄ごとの売買を確認
    for ticker in trades_df["ticker"].unique():
        ticker_trades = trades_df[trades_df["ticker"] == ticker].sort_values("date")

        print(f"\n【{ticker}の売買】")
        for _, trade in ticker_trades.iterrows():
            print(
                f"{trade['date'].strftime('%Y-%m-%d')} {trade['type']:4} "
                f"{trade['shares']:5}株 @ {trade['price']:8.2f}円 - {trade['reason']}"
            )


def check_quick_exit():
    """即日決済の原因を調査"""
    print("\n\n=== 即日・短期決済の分析 ===\n")

    # ポジションデータ
    position_files = sorted(Path("data/results").glob("positions_*.csv"))
    if not position_files:
        return

    df = pd.read_csv(position_files[-1])
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["holding_days"] = (df["exit_date"] - df["entry_date"]).dt.days

    # 短期決済（5日以内）を抽出
    short_positions = df[df["holding_days"] <= 5]

    if len(short_positions) > 0:
        print(f"短期決済ポジション: {len(short_positions)}件")

        for _, pos in short_positions.iterrows():
            print(f"\n{pos['ticker']}: {pos['holding_days']}日保有")
            print(f"  決済理由: {pos['exit_reason']}")
            print(f"  エントリー価格: {pos['entry_price']:.2f}円")
            print(f"  決済価格: {pos['exit_price']:.2f}円")

            # 価格変動率
            price_change = (pos["exit_price"] - pos["entry_price"]) / pos["entry_price"]
            print(f"  価格変動: {price_change:.2%}")


if __name__ == "__main__":
    analyze_positions_detail()
    check_dividend_dates()
    analyze_trades()
    check_quick_exit()
