#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
シンプルな修正実行スクリプト
最小限の変更で現実的な結果を得る
"""

import subprocess
import sys
from pathlib import Path
import shutil


def clear_cache():
    """キャッシュをクリア"""
    print("1. キャッシュをクリアしています...")
    cache_dir = Path("data/cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        print("   ✓ キャッシュをクリアしました")
    else:
        print("   - キャッシュディレクトリが存在しません")


def create_simple_config():
    """シンプルな修正設定を作成"""
    print("\n2. 修正版設定ファイルを作成しています...")
    
    config_content = """# シンプル修正版設定
# より現実的な結果を得るための最小限の調整

backtest:
  start_date: "2023-01-01"
  end_date: "2023-12-31"
  initial_capital: 10_000_000

data_source:
  primary: "yfinance"
  cache_dir: "./data/cache"
  cache_expire_hours: 24

strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
    max_positions: 5
  
  addition:
    enabled: false  # 買い増しを無効化（シンプル化）
    add_ratio: 0.0
    add_on_drop: false
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.1
    take_profit_on_window_fill: false  # 窓埋め判定を無効化

execution:
  slippage: 0.005  # 0.5%（現実的な値）
  slippage_ex_date: 0.01  # 1%（権利落ち日）
  commission: 0.001  # 0.1%
  min_commission: 550
  max_commission: 1100
  tax_rate: 0.20315

universe:
  # 配当が確実にある主要銘柄のみ
  tickers:
    - "7203"  # トヨタ自動車
    - "8306"  # 三菱UFJフィナンシャル
    - "8058"  # 三菱商事

logging:
  level: "INFO"
  file: "./logs/backtest_simple.log"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

output:
  results_dir: "./data/results/simple"
  report_format: ["json", "csv"]
  save_trades: true
  save_portfolio_history: true
"""
    
    config_path = Path("config/simple_config.yaml")
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"   ✓ {config_path} を作成しました")
    return str(config_path)


def run_simple_backtest():
    """シンプルなバックテストを実行"""
    print("\n3. バックテストを実行しています...")
    
    config_path = create_simple_config()
    
    # mainを実行
    cmd = [sys.executable, "main.py", "--config", config_path, "--no-viz"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ バックテストが完了しました")
            
            # 結果の一部を表示
            output_lines = result.stdout.split('\n')
            
            # 結果サマリーを探す
            in_summary = False
            for line in output_lines:
                if "バックテスト結果サマリー" in line:
                    in_summary = True
                if in_summary and line.strip():
                    print(f"   {line}")
            
        else:
            print("   ❌ バックテストでエラーが発生しました")
            print(result.stderr)
            
    except Exception as e:
        print(f"   ❌ 実行エラー: {e}")


def check_results():
    """結果の確認"""
    print("\n4. 結果を確認しています...")
    
    results_dir = Path("data/results/simple")
    if results_dir.exists():
        # 最新のメトリクスファイルを探す
        metrics_files = list(results_dir.glob("metrics_*.json"))
        
        if metrics_files:
            latest_metrics = max(metrics_files, key=lambda x: x.stat().st_mtime)
            
            import json
            with open(latest_metrics, 'r') as f:
                metrics = json.load(f)
            
            print("\n   【結果サマリー】")
            print(f"   総リターン: {metrics.get('total_return', 0):.2%}")
            print(f"   年率リターン: {metrics.get('annualized_return', 0):.2%}")
            print(f"   最大ドローダウン: {metrics.get('max_drawdown', 0):.2%}")
            print(f"   勝率: {metrics.get('win_rate', 0):.1%}")
            print(f"   総取引数: {metrics.get('total_trades', 0)}")
            
            # 現実的かチェック
            print("\n   【妥当性評価】")
            annual_return = metrics.get('annualized_return', 0)
            if -0.1 <= annual_return <= 0.1:
                print("   ✅ 年率リターンは現実的な範囲です")
            else:
                print(f"   ⚠️ 年率リターンが異常です: {annual_return:.1%}")
                
            win_rate = metrics.get('win_rate', 0)
            if 0.3 <= win_rate <= 0.7:
                print("   ✅ 勝率は現実的な範囲です")
            else:
                print(f"   ⚠️ 勝率が異常です: {win_rate:.1%}")


def main():
    """メイン処理"""
    print("配当取り戦略バックテスト - シンプル修正版")
    print("=" * 60)
    print("最小限の変更で現実的な結果を目指します")
    print()
    
    # 実行確認
    response = input("実行しますか？ (y/n): ")
    if response.lower() != 'y':
        print("キャンセルしました")
        return
    
    print()
    
    # 処理実行
    clear_cache()
    run_simple_backtest()
    check_results()
    
    print("\n" + "=" * 60)
    print("完了しました")
    print("\n詳細な結果は data/results/simple/ に保存されています")


if __name__ == "__main__":
    main()
