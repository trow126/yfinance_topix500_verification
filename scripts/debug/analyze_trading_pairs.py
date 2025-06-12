#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
取引ペアリング分析スクリプト
BUY/SELLの記録から実際の取引ペアを分析
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def analyze_trading_pairs():
    """BUY/SELLのペアリングを分析"""
    print("=== 取引ペアリング分析 ===\n")
    
    # 最新のファイルを取得
    results_dir = Path("data/results")
    trade_files = sorted(results_dir.glob("trades_*.csv"))
    
    if not trade_files:
        print("取引ファイルが見つかりません")
        return
    
    latest_file = trade_files[-1]
    print(f"対象ファイル: {latest_file}\n")
    
    # データ読み込み
    df = pd.read_csv(latest_file)
    df['date'] = pd.to_datetime(df['date'])
    
    # 銘柄ごとに分析
    tickers = df['ticker'].unique()
    
    for ticker in tickers:
        ticker_df = df[df['ticker'] == ticker].sort_values('date')
        
        print(f"\n【銘柄: {ticker}】")
        buys = ticker_df[ticker_df['type'] == 'BUY']
        sells = ticker_df[ticker_df['type'] == 'SELL']
        
        print(f"BUY: {len(buys)}回")
        print(f"SELL: {len(sells)}回")
        
        # ペアリングを試みる
        if len(buys) > 0 and len(sells) > 0:
            for i, (_, buy) in enumerate(buys.iterrows()):
                # 対応するSELLを探す
                matching_sells = sells[sells['date'] >= buy['date']]
                
                if len(matching_sells) > 0:
                    sell = matching_sells.iloc[0]
                    
                    # 保有期間を計算
                    holding_days = (sell['date'] - buy['date']).days
                    
                    # リターンを計算
                    buy_cost = buy['amount'] + buy['commission']
                    sell_proceeds = sell['amount'] - sell['commission']
                    pnl = sell_proceeds - buy_cost
                    return_rate = pnl / buy_cost
                    
                    print(f"\n  取引ペア {i+1}:")
                    print(f"    エントリー: {buy['date'].strftime('%Y-%m-%d')} @ {buy['price']:.2f}円")
                    print(f"    決済: {sell['date'].strftime('%Y-%m-%d')} @ {sell['price']:.2f}円")
                    print(f"    保有期間: {holding_days}日")
                    print(f"    リターン: {return_rate:.2%}")
                    print(f"    理由: {sell['reason']}")
    
    # 全体統計
    print("\n\n【全体統計】")
    total_buys = len(df[df['type'] == 'BUY'])
    total_sells = len(df[df['type'] == 'SELL'])
    
    print(f"総BUY数: {total_buys}")
    print(f"総SELL数: {total_sells}")
    
    if total_buys != total_sells:
        print(f"\n⚠️ BUYとSELLの数が一致しません！")
        print(f"未決済ポジション: {total_buys - total_sells}")

def check_same_day_trades():
    """同日売買をチェック"""
    print("\n\n=== 同日売買のチェック ===\n")
    
    results_dir = Path("data/results")
    trade_files = sorted(results_dir.glob("trades_*.csv"))
    latest_file = trade_files[-1]
    
    df = pd.read_csv(latest_file)
    df['date'] = pd.to_datetime(df['date'])
    
    # 日付ごとにグループ化
    date_groups = df.groupby(['date', 'ticker', 'type']).size().reset_index(name='count')
    
    # 同じ日に同じ銘柄でBUYとSELLがあるケースを探す
    for date in df['date'].unique():
        date_df = df[df['date'] == date]
        tickers_on_date = date_df['ticker'].unique()
        
        for ticker in tickers_on_date:
            ticker_date_df = date_df[date_df['ticker'] == ticker]
            
            has_buy = any(ticker_date_df['type'] == 'BUY')
            has_sell = any(ticker_date_df['type'] == 'SELL')
            
            if has_buy and has_sell:
                print(f"⚠️ 同日売買発見: {date.strftime('%Y-%m-%d')} - 銘柄{ticker}")
                print(ticker_date_df[['type', 'price', 'shares', 'reason']])

if __name__ == "__main__":
    analyze_trading_pairs()
    check_same_day_trades()
