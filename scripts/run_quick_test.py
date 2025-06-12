#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡易バックテスト実行スクリプト
修正後のシステムで小規模なテストを実行
"""

import sys
import os

# プロジェクトルートをパスに追加（1つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config, Config
from src.backtest.engine import BacktestEngine
from datetime import datetime
import json
from pathlib import Path


def create_test_config():
    """テスト用の設定を作成"""
    # 既存の設定を読み込み
    base_config = load_config("config/config.yaml")

    # テスト用に変更
    base_config.backtest.start_date = "2023-01-01"
    base_config.backtest.end_date = "2023-12-31"
    base_config.universe.tickers = ["7203", "6758", "9433"]  # 3銘柄のみ

    return base_config


def run_quick_test():
    """クイックテストを実行"""
    print("=" * 70)
    print("配当取り戦略バックテスト - クイックテスト")
    print("=" * 70)

    # 設定
    config = create_test_config()

    print(f"\n実行条件:")
    print(f"  期間: {config.backtest.start_date} ～ {config.backtest.end_date}")
    print(f"  銘柄: {', '.join(config.universe.tickers)}")
    print(f"  初期資本: {config.backtest.initial_capital:,}円")

    # キャッシュクリアの確認
    cache_dir = Path(config.data_source.cache_dir)
    if cache_dir.exists() and any(cache_dir.iterdir()):
        response = input("\nキャッシュが存在します。クリアしますか？ (y/n): ")
        if response.lower() == "y":
            import shutil

            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            print("キャッシュをクリアしました。")

    # バックテスト実行
    print("\nバックテストを開始します...")
    start_time = datetime.now()

    try:
        engine = BacktestEngine(config)
        results = engine.run()

        # 実行時間
        execution_time = (datetime.now() - start_time).total_seconds()

        # 結果表示
        print("\n" + "=" * 70)
        print("バックテスト結果")
        print("=" * 70)

        metrics = results["metrics"]

        print(f"\n【リターン指標】")
        print(f"  総リターン: {metrics.get('total_return', 0):.2%}")
        print(f"  年率リターン: {metrics.get('annualized_return', 0):.2%}")

        print(f"\n【リスク指標】")
        print(f"  最大ドローダウン: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  シャープレシオ: {metrics.get('sharpe_ratio', 0):.2f}")

        print(f"\n【取引統計】")
        print(f"  総取引数: {metrics.get('total_trades', 0)}")
        print(f"  勝率: {metrics.get('win_rate', 0):.1%}")
        print(f"  平均保有期間: {metrics.get('avg_holding_days', 0):.1f}日")

        print(f"\n【実行情報】")
        print(f"  実行時間: {execution_time:.1f}秒")

        # 警告チェック
        print("\n【妥当性チェック】")
        warnings = []

        if metrics.get("annualized_return", 0) > 0.15:
            warnings.append(
                "年率リターンが15%を超えています - 設定を再確認してください"
            )

        if metrics.get("win_rate", 0) > 0.65:
            warnings.append(
                "勝率が65%を超えています - 取引コストが低すぎる可能性があります"
            )

        if abs(metrics.get("max_drawdown", 0)) < 0.05:
            warnings.append(
                "最大ドローダウンが5%未満です - リスクが過小評価されている可能性があります"
            )

        if warnings:
            print("  ⚠️  " + "\n  ⚠️  ".join(warnings))
        else:
            print("  ✅ 結果は妥当な範囲内です")

        # 結果ファイルの場所
        print(f"\n詳細な結果は以下に保存されました:")
        results_dir = Path(config.output.results_dir)
        latest_files = sorted(results_dir.glob("*"))[-5:]
        for file in latest_files:
            print(f"  - {file}")

    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    return True


def check_environment():
    """実行環境をチェック"""
    print("\n環境チェック:")

    # Python バージョン
    print(f"  Python: {sys.version.split()[0]}")

    # 必要なパッケージ
    required_packages = ["yfinance", "pandas", "numpy", "matplotlib"]
    for package in required_packages:
        try:
            __import__(package)
            print(f"  {package}: ✓")
        except ImportError:
            print(f"  {package}: ✗ (要インストール)")

    # メモリ
    try:
        import psutil

        mem = psutil.virtual_memory()
        print(f"  利用可能メモリ: {mem.available / (1024**3):.1f} GB")
    except:
        print("  メモリ情報: 取得できません")


if __name__ == "__main__":
    check_environment()

    print("\n修正後のバックテストシステムでクイックテストを実行します。")
    print("このテストは3銘柄、1年間の小規模なテストです。")

    success = run_quick_test()

    if success:
        print("\n\n次のステップ:")
        print("1. 結果を確認して妥当性を検証")
        print("2. より大規模なバックテストを実行:")
        print("   python main.py")
        print("3. TOPIX500全銘柄でのバックテスト:")
        print("   python run_topix500_backtest.py")
