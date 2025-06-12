#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細デバッグ - 取引フローを追跡
"""

import pandas as pd
from pathlib import Path


def trace_trading_flow():
    """取引フローを詳細に追跡"""
    print("=== 取引フローの詳細追跡 ===\n")
    
    # 最新の取引データを読み込み
    trades_file = Path("data/results/simple/trades_20250612_125740.csv")
    
    if not trades_file.exists():
        print("取引ファイルが見つかりません")
        return
    
    trades_df = pd.read_csv(trades_file)
    trades_df['date'] = pd.to_datetime(trades_df['date'])
    
    # 銘柄ごとに時系列で確認
    for ticker in trades_df['ticker'].unique():
        print(f"\n【{ticker}の取引フロー】")
        ticker_trades = trades_df[trades_df['ticker'] == ticker].sort_values('date')
        
        cumulative_shares = 0
        
        for idx, trade in ticker_trades.iterrows():
            if trade['type'] == 'BUY':
                cumulative_shares += trade['shares']
                action = f"+{trade['shares']}"
            else:
                action = f"-{trade['shares']}"
                cumulative_shares -= trade['shares']
            
            print(f"{trade['date'].strftime('%Y-%m-%d')} | {trade['type']:4} | {action:6} | 累計: {cumulative_shares:4} | {trade['reason']}")
        
        if cumulative_shares != 0:
            print(f"\n⚠️ 最終累計株数が0ではありません: {cumulative_shares}")


def check_data_integrity():
    """データの整合性をチェック"""
    print("\n\n=== データ整合性チェック ===\n")
    
    # 同じトレードファイルを違う方法で確認
    trades_file = Path("data/results/simple/trades_20250612_125740.csv")
    trades_df = pd.read_csv(trades_file)
    
    # reasonカラムをチェック
    print("【取引理由の集計】")
    reason_counts = trades_df['reason'].value_counts()
    for reason, count in reason_counts.items():
        print(f"{reason}: {count}件")
    
    # 買い増しがあるかチェック
    add_trades = trades_df[trades_df['reason'].str.contains('Add', na=False)]
    if len(add_trades) > 0:
        print(f"\n⚠️ 買い増し取引が見つかりました: {len(add_trades)}件")
        print(add_trades)
    else:
        print("\n✓ 買い増し取引はありません")


def create_debug_version():
    """デバッグ版のengine.pyを作成"""
    print("\n\n=== デバッグ版engine.pyの修正案 ===\n")
    
    debug_code = '''
# src/backtest/engine.py の _process_existing_positions メソッドを修正

def _process_existing_positions(self, current_date, current_prices):
    """既存ポジションの処理（修正版）"""
    positions = self.portfolio.position_manager.get_open_positions()
    
    for position in positions:
        ticker = position.ticker
        
        if ticker not in current_prices:
            continue
        
        current_price = current_prices[ticker]
        
        # デバッグ: 現在の株数を記録
        log.info(f"{ticker}: 現在の株数 = {position.total_shares}")
        
        # ポジション情報を辞書形式に変換
        position_info = {
            'entry_date': position.entry_date,
            'entry_price': position.entry_price,
            'average_price': position.average_price,
            'total_shares': position.total_shares,
            'initial_value': position.entry_price * position.total_shares,
            'ex_dividend_date': position.ex_dividend_date,
            'pre_ex_price': position.pre_ex_price or position.entry_price
        }
        
        # 決済シグナルをチェック
        exit_signal = self.strategy.check_exit_signal(
            ticker=ticker,
            current_date=current_date,
            position_info=position_info,
            current_price=current_price
        )
        
        if exit_signal:
            # デバッグ: 決済前の株数を記録
            log.info(f"{ticker}: 決済シグナル - 株数 = {exit_signal.shares}")
            self._execute_exit(exit_signal, current_price)
            continue
        
        # 買い増し処理をコメントアウト（完全に無効化）
        """
        # 買い増しシグナルをチェック（権利落ち日のみ）
        if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
            log.warning(f"{ticker}: 権利落ち日処理（無効化されているはず）")
        """
'''
    
    print(debug_code)


def check_duplicate_dates():
    """同じ日付での重複処理をチェック"""
    print("\n\n=== 日付重複チェック ===\n")
    
    # ポートフォリオ履歴を確認
    portfolio_file = Path("data/results/simple/portfolio_20250612_125740.csv")
    
    if portfolio_file.exists():
        portfolio_df = pd.read_csv(portfolio_file, index_col=0)
        
        # 日付ごとのposition_countの変化を確認
        print("【ポジション数の推移】")
        prev_count = 0
        
        for date, row in portfolio_df.iterrows():
            current_count = row['position_count']
            if current_count != prev_count:
                print(f"{date}: {prev_count} → {current_count}")
                prev_count = current_count


if __name__ == "__main__":
    trace_trading_flow()
    check_data_integrity()
    create_debug_version()
    check_duplicate_dates()
