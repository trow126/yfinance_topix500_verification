#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バックテスト問題診断スクリプト
異常な結果の原因を特定する
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import yfinance as yf


def check_trade_details():
    """最新の取引履歴を詳細にチェック"""
    print("=== 取引履歴の詳細チェック ===\n")

    # 最新の取引ファイルを取得
    results_dir = Path("data/results")
    trade_files = sorted(results_dir.glob("trades_*.csv"))

    if not trade_files:
        print("取引ファイルが見つかりません")
        return

    latest_trades = trade_files[-1]
    print(f"分析対象: {latest_trades}\n")

    # 取引データを読み込み
    trades_df = pd.read_csv(latest_trades)

    print("【取引サマリー】")
    print(f"総取引数: {len(trades_df)}")
    print(f"平均保有期間: {trades_df['holding_days'].mean():.1f}日")
    print(f"平均リターン: {trades_df['return_rate'].mean():.2%}")

    print("\n【異常な取引の検出】")

    # 保有期間0日の取引
    zero_day_trades = trades_df[trades_df["holding_days"] == 0]
    if len(zero_day_trades) > 0:
        print(f"⚠️ 保有期間0日の取引: {len(zero_day_trades)}件")
        print(
            zero_day_trades[["ticker", "entry_date", "exit_date", "return_rate"]].head()
        )

    # 異常に高いリターンの取引
    high_return_trades = trades_df[trades_df["return_rate"] > 0.1]  # 10%以上
    if len(high_return_trades) > 0:
        print(f"\n⚠️ 高リターン取引（10%以上）: {len(high_return_trades)}件")
        print(high_return_trades[["ticker", "return_rate", "holding_days"]].head())

    return trades_df


def check_price_data_adjustment():
    """価格データの調整状況をチェック"""
    print("\n\n=== 価格データ調整チェック ===\n")

    # テスト銘柄
    test_ticker = "7203.T"

    # 最近の配当落ち日周辺のデータを取得
    stock = yf.Ticker(test_ticker)

    # 調整済みと未調整の両方を取得
    print(f"テスト銘柄: {test_ticker}")

    # 2023年9月の例
    start = "2023-09-20"
    end = "2023-09-30"

    # 調整済み
    adj_hist = stock.history(start=start, end=end, auto_adjust=True)
    adj_hist.index = adj_hist.index.tz_localize(None)

    # 未調整
    unadj_hist = stock.history(start=start, end=end, auto_adjust=False)
    unadj_hist.index = unadj_hist.index.tz_localize(None)

    print("\n【価格比較】")
    print("日付         | 調整済み  | 未調整    | 差額")
    print("-" * 50)

    for date in adj_hist.index[:5]:
        adj_price = adj_hist.loc[date, "Close"]
        unadj_price = unadj_hist.loc[date, "Close"]
        diff = unadj_price - adj_price
        print(
            f"{date.strftime('%Y-%m-%d')} | {adj_price:8.2f} | {unadj_price:8.2f} | {diff:6.2f}"
        )


def check_yfinance_client_code():
    """YFinanceClientのコードを確認"""
    print("\n\n=== YFinanceClientコード確認 ===\n")

    try:
        with open("src/data/yfinance_client.py", "r", encoding="utf-8") as f:
            content = f.read()

        # auto_adjust=Falseが含まれているか確認
        if "auto_adjust=False" in content:
            print("✅ auto_adjust=False が設定されています")

            # 該当行を表示
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "auto_adjust=False" in line:
                    print(f"\n行{i + 1}: {line.strip()}")
        else:
            print("❌ auto_adjust=False が見つかりません！")

            # historyメソッドの呼び出しを探す
            for i, line in enumerate(lines):
                if "history(" in line and "stock" in line:
                    print(f"\n行{i + 1}: {line.strip()}")

    except FileNotFoundError:
        print("yfinance_client.pyが見つかりません")


def check_cache_status():
    """キャッシュの状態を確認"""
    print("\n\n=== キャッシュ状態チェック ===\n")

    cache_dir = Path("data/cache")

    if not cache_dir.exists():
        print("キャッシュディレクトリが存在しません")
        return

    cache_files = list(cache_dir.glob("*"))
    print(f"キャッシュファイル数: {len(cache_files)}")

    if cache_files:
        # 最も古いファイル
        oldest = min(cache_files, key=lambda p: p.stat().st_mtime)
        oldest_time = datetime.fromtimestamp(oldest.stat().st_mtime)

        # 最も新しいファイル
        newest = max(cache_files, key=lambda p: p.stat().st_mtime)
        newest_time = datetime.fromtimestamp(newest.stat().st_mtime)

        print(f"最古のキャッシュ: {oldest_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"最新のキャッシュ: {newest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # .metaファイルの内容を確認
        meta_files = list(cache_dir.glob("*.meta"))
        if meta_files:
            print(f"\n.metaファイルをチェック...")
            sample_meta = meta_files[0]
            with open(sample_meta, "r") as f:
                meta_content = json.load(f)
                print(f"サンプル: {sample_meta.name}")
                print(f"  タイムスタンプ: {meta_content.get('timestamp', 'N/A')}")
                print(f"  データタイプ: {meta_content.get('data_type', 'N/A')}")


def check_execution_logic():
    """実行ロジックの問題をチェック"""
    print("\n\n=== 実行ロジックチェック ===\n")

    # 保有期間の計算ロジックを確認
    print("【保有期間0日の原因】")
    print("可能性1: エントリー日と決済日が同じ")
    print("可能性2: 営業日計算のバグ")
    print("可能性3: 即座に損切りラインに達している")

    # 設定ファイルを確認
    try:
        import yaml

        with open("config/config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        print("\n【現在の設定】")
        print(f"損切りライン: {config['strategy']['exit']['stop_loss_pct'] * 100:.0f}%")
        print(f"最大保有期間: {config['strategy']['exit']['max_holding_days']}日")
        print(f"スリッページ: {config['execution']['slippage'] * 100:.1f}%")

        # 手数料設定の確認
        if "tax_rate" in config["execution"]:
            print(f"配当税率: {config['execution']['tax_rate'] * 100:.1f}%")
        else:
            print("⚠️ 配当税率が設定されていません")

    except Exception as e:
        print(f"設定ファイルの読み込みエラー: {e}")


def main():
    """診断を実行"""
    print("配当取り戦略バックテスト - 問題診断")
    print("=" * 70)

    # 1. 取引詳細のチェック
    trades_df = check_trade_details()

    # 2. 価格データ調整のチェック
    check_price_data_adjustment()

    # 3. コードの確認
    check_yfinance_client_code()

    # 4. キャッシュ状態の確認
    check_cache_status()

    # 5. 実行ロジックのチェック
    check_execution_logic()

    print("\n\n=== 診断結果と推奨アクション ===")
    print("\n1. キャッシュを完全にクリア:")
    print("   del /s /q data\\cache\\*")

    print("\n2. 検証スクリプトを実行:")
    print("   python scripts/verify_adjustments.py")

    print("\n3. デバッグモードで再実行:")
    print("   python main.py --log-level DEBUG")

    print("\n4. 必要に応じてコードを確認:")
    print("   - src/data/yfinance_client.py")
    print("   - src/backtest/engine.py")
    print("   - src/strategy/dividend_strategy.py")


if __name__ == "__main__":
    main()
