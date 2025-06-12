#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
取引履歴の簡易確認スクリプト
CSVファイルの構造を確認する
"""

import pandas as pd
from pathlib import Path
import sys

def check_csv_structure():
    """CSVファイルの構造を確認"""
    print("=== 取引履歴CSVの構造確認 ===\n")
    
    # 最新の取引ファイルを取得
    results_dir = Path("data/results")
    trade_files = sorted(results_dir.glob("trades_*.csv"))
    
    if not trade_files:
        print("取引ファイルが見つかりません")
        return
    
    latest_trades = trade_files[-1]
    print(f"対象ファイル: {latest_trades}")
    
    # CSVを読み込み
    try:
        df = pd.read_csv(latest_trades)
        
        print(f"\n行数: {len(df)}")
        print(f"\nカラム一覧:")
        for i, col in enumerate(df.columns):
            print(f"  {i+1}. {col}")
        
        print("\n最初の3行:")
        print(df.head(3))
        
        # 数値カラムの統計
        print("\n数値カラムの統計:")
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            print(f"\n{col}:")
            print(f"  平均: {df[col].mean():.2f}")
            print(f"  最小: {df[col].min():.2f}")
            print(f"  最大: {df[col].max():.2f}")
        
        # 日付カラムの確認
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        if date_cols:
            print("\n日付カラム:")
            for col in date_cols:
                print(f"  {col}: {df[col].iloc[0]} ～ {df[col].iloc[-1]}")
                
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_csv_structure()
