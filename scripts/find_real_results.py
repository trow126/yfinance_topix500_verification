#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポジションサマリーの確認
実際の取引結果（保有期間、リターン率）を確認
"""

import pandas as pd
from pathlib import Path
import json

def find_positions_summary():
    """positions_*.csvファイルを探す"""
    print("=== ポジションサマリーファイルの検索 ===\n")
    
    results_dir = Path("data/results")
    
    # positions_*.csv を探す
    position_files = list(results_dir.glob("positions_*.csv"))
    
    if position_files:
        print(f"ポジションファイル発見: {len(position_files)}個")
        
        latest = sorted(position_files)[-1]
        print(f"\n最新ファイル: {latest}")
        
        # 読み込んで表示
        df = pd.read_csv(latest)
        print(f"\nポジション数: {len(df)}")
        print(f"\nカラム:")
        for col in df.columns:
            print(f"  - {col}")
        
        print("\n【ポジション詳細】")
        print(df)
        
        # 統計情報
        if 'realized_pnl' in df.columns:
            print(f"\n総実現損益: {df['realized_pnl'].sum():,.0f}円")
            print(f"平均実現損益: {df['realized_pnl'].mean():,.0f}円")
        
        # 保有期間の計算
        if 'entry_date' in df.columns and 'exit_date' in df.columns:
            df['entry_date'] = pd.to_datetime(df['entry_date'])
            df['exit_date'] = pd.to_datetime(df['exit_date'])
            df['holding_days'] = (df['exit_date'] - df['entry_date']).dt.days
            
            print(f"\n平均保有期間: {df['holding_days'].mean():.1f}日")
            print(f"最短保有期間: {df['holding_days'].min()}日")
            print(f"最長保有期間: {df['holding_days'].max()}日")
        
        return df
    else:
        print("ポジションサマリーファイルが見つかりません")
        print("\n利用可能なファイル:")
        for f in sorted(results_dir.glob("*.csv")):
            print(f"  - {f.name}")
        
        return None

def calculate_actual_returns(positions_df):
    """実際のリターンを計算"""
    if positions_df is None:
        return
    
    print("\n\n=== 実際のリターン計算 ===")
    
    # 投資額とリターンの計算
    if 'entry_price' in positions_df.columns and 'total_shares' in positions_df.columns:
        positions_df['investment'] = positions_df['entry_price'] * positions_df['total_shares']
        
        if 'realized_pnl' in positions_df.columns:
            positions_df['return_rate'] = positions_df['realized_pnl'] / positions_df['investment']
            
            print(f"\n平均リターン率: {positions_df['return_rate'].mean():.2%}")
            print(f"勝率: {(positions_df['return_rate'] > 0).mean():.1%}")
            
            # 年率換算（簡易計算）
            if 'holding_days' in positions_df:
                positions_df['annualized_return'] = (1 + positions_df['return_rate']) ** (365 / positions_df['holding_days']) - 1
                
                # 異常値を除外（保有期間0日など）
                valid_returns = positions_df[positions_df['holding_days'] > 0]['annualized_return']
                
                if len(valid_returns) > 0:
                    print(f"\n年率換算リターン（平均）: {valid_returns.mean():.2%}")
                    print(f"年率換算リターン（中央値）: {valid_returns.median():.2%}")

def check_metrics_file():
    """メトリクスファイルの内容を確認"""
    print("\n\n=== メトリクスファイルの確認 ===")
    
    results_dir = Path("data/results")
    metrics_files = list(results_dir.glob("metrics_*.json"))
    
    if metrics_files:
        latest = sorted(metrics_files)[-1]
        print(f"\n最新メトリクス: {latest}")
        
        with open(latest, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        # 重要な指標を表示
        important_keys = ['total_return', 'annualized_return', 'total_trades', 
                         'win_rate', 'sharpe_ratio', 'max_drawdown']
        
        for key in important_keys:
            if key in metrics:
                value = metrics[key]
                if isinstance(value, (int, float)):
                    if 'return' in key or 'rate' in key:
                        print(f"{key}: {value:.2%}")
                    else:
                        print(f"{key}: {value:.2f}")

if __name__ == "__main__":
    # ポジションサマリーを探す
    positions_df = find_positions_summary()
    
    # 実際のリターンを計算
    calculate_actual_returns(positions_df)
    
    # メトリクスファイルも確認
    check_metrics_file()
