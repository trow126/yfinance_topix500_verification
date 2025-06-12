#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小限のデバッグテスト
トヨタ1銘柄のみで問題を特定
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import sys
import os
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def check_toyota_data():
    """トヨタのデータを詳細確認"""
    print("=== トヨタ（7203）のデータ確認 ===\n")
    
    ticker = yf.Ticker("7203.T")
    
    # 2023年3月の価格データ
    start = "2023-03-20"
    end = "2023-04-30"
    
    hist = ticker.history(start=start, end=end, auto_adjust=False)
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    
    print("【価格データ（2023年3月-4月）】")
    print("日付         | 終値      | 出来高    | 配当    | 分割")
    print("-" * 60)
    
    for date, row in hist.iterrows():
        close = row['Close']
        volume = row['Volume']
        dividend = row.get('Dividends', 0)
        split = row.get('Stock Splits', 0)
        
        date_str = date.strftime('%Y-%m-%d')
        
        if dividend > 0 or split > 0:
            print(f"{date_str} | {close:8.2f} | {volume:9.0f} | {dividend:6.2f} | {split:4.1f} ⬅️")
        else:
            print(f"{date_str} | {close:8.2f} | {volume:9.0f} |        |")
    
    # 株式分割の確認
    splits = ticker.splits
    if not splits.empty:
        print("\n【株式分割履歴】")
        for date, ratio in splits.items():
            print(f"{date.strftime('%Y-%m-%d')}: 1:{ratio}")


def run_minimal_test():
    """最小限のテストを実行"""
    print("\n\n=== 最小限テスト実行 ===\n")
    
    config_content = """# 最小限テスト - トヨタ1銘柄のみ
backtest:
  start_date: "2023-03-20"
  end_date: "2023-04-30"
  initial_capital: 10_000_000

data_source:
  primary: "yfinance"
  cache_dir: "./data/cache_minimal"
  cache_expire_hours: 1

strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
    max_positions: 1
  
  addition:
    enabled: false
    add_ratio: 0.0
    add_on_drop: false
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.15  # 15%に緩和
    take_profit_on_window_fill: false

execution:
  slippage: 0.0  # スリッページを0に
  slippage_ex_date: 0.0
  commission: 0.0  # 手数料も0に
  min_commission: 0
  max_commission: 0
  tax_rate: 0.0  # 税金も0に

universe:
  tickers:
    - "7203"  # トヨタのみ

logging:
  level: "DEBUG"
  file: "./logs/minimal_debug.log"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {function} | {message}"

output:
  results_dir: "./data/results/minimal_debug"
  report_format: ["json", "csv"]
  save_trades: true
  save_portfolio_history: true
"""
    
    # 設定ファイル作成
    config_path = "config/minimal_debug.yaml"
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"設定ファイル作成: {config_path}")
    
    # キャッシュクリア
    import shutil
    cache_dir = "./data/cache_minimal"
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    
    print("\n実行コマンド:")
    print(f"python main.py --config {config_path} --no-viz")
    
    # 実行
    response = input("\n実行しますか？ (y/n): ")
    if response.lower() == 'y':
        import subprocess
        result = subprocess.run(
            [sys.executable, "main.py", "--config", config_path, "--no-viz"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("\n実行完了")
            
            # 結果確認
            from pathlib import Path
            results_dir = Path("data/results/minimal_debug")
            
            # 取引履歴を確認
            trades_files = list(results_dir.glob("trades_*.csv"))
            if trades_files:
                latest_trades = max(trades_files, key=lambda x: x.stat().st_mtime)
                
                print(f"\n取引履歴: {latest_trades}")
                trades_df = pd.read_csv(latest_trades)
                print(trades_df)
                
                # 株数の確認
                buy_shares = trades_df[trades_df['type'] == 'BUY']['shares'].sum()
                sell_shares = trades_df[trades_df['type'] == 'SELL']['shares'].sum()
                
                print(f"\n買い株数合計: {buy_shares}")
                print(f"売り株数合計: {sell_shares}")
                
                if sell_shares != buy_shares:
                    print(f"⚠️ 差分: {sell_shares - buy_shares}株")
        else:
            print(f"\nエラー: {result.stderr}")


def check_position_manager_code():
    """PositionManagerのコードを確認"""
    print("\n\n=== PositionManagerコードの確認ポイント ===\n")
    
    print("1. total_sharesの更新箇所を確認")
    print("2. add_to_positionメソッドが呼ばれていないか")
    print("3. trade_countの増加タイミング")
    print("4. 売却時の株数取得方法")


if __name__ == "__main__":
    check_toyota_data()
    run_minimal_test()
    check_position_manager_code()
