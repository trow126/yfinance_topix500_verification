#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
即座の修正対応スクリプト
異常な結果を修正するための即効性のある対策
"""

import os
import sys
import shutil
from pathlib import Path


def clear_all_cache():
    """すべてのキャッシュをクリア"""
    print("=== キャッシュの完全クリア ===\n")
    
    cache_dir = Path("data/cache")
    
    if cache_dir.exists():
        file_count = len(list(cache_dir.glob("*")))
        print(f"キャッシュファイル数: {file_count}")
        
        # 確認
        response = input("\nすべてのキャッシュをクリアしますか？ (y/n): ")
        if response.lower() == 'y':
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            print("✓ キャッシュをクリアしました")
        else:
            print("キャンセルしました")
    else:
        print("キャッシュディレクトリが存在しません")


def update_dependencies():
    """依存パッケージの更新"""
    print("\n\n=== 依存パッケージの更新 ===\n")
    
    packages = [
        "yfinance",
        "pandas",
        "numpy",
        "jpholiday"
    ]
    
    print("以下のパッケージを更新します:")
    for pkg in packages:
        print(f"  - {pkg}")
    
    response = input("\n更新を実行しますか？ (y/n): ")
    if response.lower() == 'y':
        import subprocess
        
        for pkg in packages:
            print(f"\n更新中: {pkg}")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg], check=True)
                print(f"✓ {pkg} を更新しました")
            except subprocess.CalledProcessError:
                print(f"❌ {pkg} の更新に失敗しました")


def create_fixed_config():
    """修正版の設定ファイルを作成"""
    print("\n\n=== 修正版設定ファイルの作成 ===\n")
    
    fixed_config = """# 修正版設定ファイル - 異常値対策済み
# 現実的なバックテスト結果を得るための設定

backtest:
  start_date: "2023-01-01"
  end_date: "2023-12-31"
  initial_capital: 10_000_000

data_source:
  primary: "yfinance"
  cache_dir: "./data/cache"
  cache_expire_hours: 1  # キャッシュを短くして最新データを取得

strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
    max_positions: 5  # ポジション数を減らして管理しやすく
  
  addition:
    enabled: true
    add_ratio: 0.3  # 買い増し比率を下げる
    add_on_drop: true
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.08  # 損切りを8%に
    take_profit_on_window_fill: true
    min_holding_days: 3  # 最低保有期間を追加

execution:
  slippage: 0.003  # スリッページを0.3%に増加
  slippage_ex_date: 0.008  # 権利落ち日は0.8%
  commission: 0.001  # 手数料を0.1%に
  min_commission: 550
  max_commission: 1100
  tax_rate: 0.20315

# テスト用に確実に配当がある銘柄を選定
universe:
  tickers:
    - "7203"  # トヨタ自動車
    - "6758"  # ソニーグループ
    - "8306"  # 三菱UFJフィナンシャル
    - "9432"  # 日本電信電話（NTT）
    - "8058"  # 三菱商事

logging:
  level: "DEBUG"  # デバッグレベルで詳細ログ
  file: "./logs/backtest_fixed.log"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

output:
  results_dir: "./data/results/fixed"
  report_format: ["json", "csv", "html"]
  save_trades: true
  save_portfolio_history: true

# 追加の修正オプション
fixes:
  ignore_same_day_exit: true  # 同日決済を禁止
  require_dividend_data: true  # 配当データがない銘柄をスキップ
  use_realistic_fills: true  # より現実的な約定価格
"""
    
    config_path = Path("config/fixed_config.yaml")
    
    print(f"修正版設定ファイルを作成: {config_path}")
    response = input("\n作成しますか？ (y/n): ")
    
    if response.lower() == 'y':
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(fixed_config)
        print(f"✓ {config_path} を作成しました")
        return str(config_path)
    
    return None


def apply_code_fixes():
    """コードの即効修正案"""
    print("\n\n=== コード修正の提案 ===\n")
    
    print("1. **dividend_strategy.py の修正**")
    print("   - 最低保有期間のチェックを追加")
    print("   - 窓埋め判定に配当落ち幅を考慮")
    
    print("\n2. **yfinance_client.py の修正**")
    print("   - 配当データ取得のエラーハンドリング強化")
    print("   - 代替データソースの実装")
    
    print("\n3. **engine.py の修正**")
    print("   - 同日決済の防止")
    print("   - 配当支払い処理の改善")


def run_test_with_fixes():
    """修正を適用してテスト実行"""
    print("\n\n=== 修正版でのテスト実行 ===\n")
    
    config_path = create_fixed_config()
    
    if config_path:
        print("\n修正版設定でバックテストを実行します")
        print(f"コマンド: python main.py --config {config_path}")
        
        response = input("\n実行しますか？ (y/n): ")
        if response.lower() == 'y':
            import subprocess
            subprocess.run([sys.executable, "main.py", "--config", config_path])


def main():
    """メイン処理"""
    print("配当取り戦略バックテスト - 即効修正対応")
    print("=" * 60)
    
    actions = [
        "1. キャッシュをクリア",
        "2. 依存パッケージを更新",
        "3. 修正版設定でテスト実行",
        "4. すべて実行",
        "5. 終了"
    ]
    
    print("\n実行する操作を選択してください:")
    for action in actions:
        print(f"  {action}")
    
    choice = input("\n選択 (1-5): ")
    
    if choice == "1":
        clear_all_cache()
    elif choice == "2":
        update_dependencies()
    elif choice == "3":
        run_test_with_fixes()
    elif choice == "4":
        clear_all_cache()
        update_dependencies()
        run_test_with_fixes()
    elif choice == "5":
        print("終了します")
    else:
        print("無効な選択です")
    
    # コード修正の提案は常に表示
    apply_code_fixes()


if __name__ == "__main__":
    main()
