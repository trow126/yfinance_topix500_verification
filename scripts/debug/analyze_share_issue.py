#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
株数異常の詳細調査スクリプト
"""

import pandas as pd
from pathlib import Path


def analyze_share_count_issue():
    """株数の異常を詳細分析"""
    print("=== 株数異常の詳細分析 ===\n")
    
    # 最新の取引ファイルを読み込み
    trades_file = Path("data/results/simple/trades_20250612_125740.csv")
    positions_file = Path("data/results/simple/positions_20250612_125740.csv")
    
    if not trades_file.exists():
        print("取引ファイルが見つかりません")
        return
    
    trades_df = pd.read_csv(trades_file)
    positions_df = pd.read_csv(positions_file)
    
    # 銘柄ごとに分析
    for ticker in trades_df['ticker'].unique():
        print(f"\n【{ticker}】")
        ticker_trades = trades_df[trades_df['ticker'] == ticker]
        
        print("取引履歴:")
        for idx, trade in ticker_trades.iterrows():
            print(f"  {trade['date']} {trade['type']:4} {trade['shares']:5}株 - {trade['reason']}")
        
        # 買い株数の合計
        buy_shares = ticker_trades[ticker_trades['type'] == 'BUY']['shares'].sum()
        sell_shares = ticker_trades[ticker_trades['type'] == 'SELL']['shares'].sum()
        
        print(f"\n株数集計:")
        print(f"  買い合計: {buy_shares}株")
        print(f"  売り合計: {sell_shares}株")
        print(f"  差分: {sell_shares - buy_shares}株")
        
        if sell_shares != buy_shares:
            print(f"  ⚠️ 売買株数が一致しません！")
            
        # ポジション情報も確認
        ticker_position = positions_df[positions_df['ticker'] == ticker]
        if not ticker_position.empty:
            print(f"\nポジション情報:")
            print(f"  total_shares: {ticker_position['total_shares'].iloc[0]}")
            print(f"  trade_count: {ticker_position['trade_count'].iloc[0]}")
            print(f"  average_price: {ticker_position['average_price'].iloc[0]:.2f}")


def check_source_code():
    """ソースコードの確認ポイント"""
    print("\n\n=== ソースコード確認ポイント ===\n")
    
    print("1. **position_manager.py**")
    print("   - add_to_position メソッドが無効化されているか")
    print("   - total_shares の更新ロジック")
    
    print("\n2. **engine.py**")
    print("   - 買い増し処理が本当に無効化されているか")
    print("   - 権利落ち日の処理")
    
    print("\n3. **portfolio.py**")
    print("   - execute_sell での株数取得方法")


def suggest_debug_code():
    """デバッグコードの提案"""
    print("\n\n=== デバッグコードの提案 ===\n")
    
    debug_code = '''
# src/backtest/engine.py の _process_existing_positions に追加
log.debug(f"{ticker}: 現在の株数 = {position.total_shares}")

# src/backtest/portfolio.py の execute_sell に追加
log.info(f"売却実行: {ticker} 株数={position.total_shares}")

# src/strategy/position_manager.py の add_to_position の最初に追加
log.warning(f"買い増し呼び出し: {ticker} 追加株数={shares}")
'''
    
    print(debug_code)
    
    print("\n4. **即効対策: 権利落ち日処理を完全に無効化**")
    print("   engineの権利落ち日チェック部分をコメントアウト")


def create_minimal_test():
    """最小限のテストケース作成"""
    print("\n\n=== 最小限のテストケース ===\n")
    
    minimal_config = '''# 最小限テスト設定
backtest:
  start_date: "2023-03-01"
  end_date: "2023-04-30"  # 2ヶ月のみ
  initial_capital: 10_000_000

data_source:
  primary: "yfinance"
  cache_dir: "./data/cache"
  cache_expire_hours: 24

strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
    max_positions: 1  # 1銘柄のみ
  
  addition:
    enabled: false
    add_ratio: 0.0
    add_on_drop: false
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.1
    take_profit_on_window_fill: false

execution:
  slippage: 0.005
  slippage_ex_date: 0.005  # 権利落ち日も同じに
  commission: 0.001
  min_commission: 550
  max_commission: 1100
  tax_rate: 0.20315

universe:
  tickers:
    - "7203"  # トヨタのみ

logging:
  level: "DEBUG"  # デバッグレベル
  file: "./logs/minimal_test.log"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

output:
  results_dir: "./data/results/minimal"
  report_format: ["json", "csv"]
  save_trades: true
  save_portfolio_history: true
'''
    
    config_path = Path("config/minimal_test.yaml")
    with open(config_path, 'w') as f:
        f.write(minimal_config)
    
    print(f"最小限テスト設定を作成: {config_path}")
    print("\n実行コマンド:")
    print("python main.py --config config/minimal_test.yaml")


if __name__ == "__main__":
    analyze_share_count_issue()
    check_source_code()
    suggest_debug_code()
    create_minimal_test()
