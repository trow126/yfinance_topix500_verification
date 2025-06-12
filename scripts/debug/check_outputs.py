#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポートフォリオ出力の確認スクリプト
バックテストの実際の出力ファイルを確認
"""

import os
from pathlib import Path
import json
import pandas as pd

def check_all_output_files():
    """すべての出力ファイルを確認"""
    print("=== バックテスト出力ファイルの確認 ===\n")
    
    results_dir = Path("data/results")
    
    if not results_dir.exists():
        print("結果ディレクトリが存在しません")
        return
    
    # ファイルタイプごとに分類
    file_types = {
        'metrics': list(results_dir.glob("metrics_*.json")),
        'trades': list(results_dir.glob("trades_*.csv")),
        'portfolio': list(results_dir.glob("portfolio_*.csv")),
        'positions': list(results_dir.glob("positions_*.csv")),
        'report': list(results_dir.glob("*report*.html"))
    }
    
    print("【ファイル一覧】")
    for ftype, files in file_types.items():
        print(f"\n{ftype}: {len(files)}ファイル")
        if files:
            # 最新のファイルを表示
            latest = sorted(files)[-1]
            print(f"  最新: {latest.name}")
    
    # メトリクスファイルを確認
    if file_types['metrics']:
        print("\n\n【最新のメトリクス】")
        latest_metrics = sorted(file_types['metrics'])[-1]
        
        with open(latest_metrics, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
            
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if 'return' in key or 'ratio' in key:
                    print(f"{key}: {value:.2%}")
                else:
                    print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
    
    # ポジション履歴があるか確認
    if file_types['positions']:
        print("\n\n【ポジション履歴の確認】")
        latest_positions = sorted(file_types['positions'])[-1]
        
        try:
            pos_df = pd.read_csv(latest_positions)
            print(f"ポジション数: {len(pos_df)}")
            print(f"カラム: {pos_df.columns.tolist()}")
            
            if len(pos_df) > 0:
                print("\n最初の3件:")
                print(pos_df.head(3))
        except Exception as e:
            print(f"読み込みエラー: {e}")

def find_position_manager_output():
    """PositionManagerの出力を探す"""
    print("\n\n=== PositionManager関連の出力を探索 ===\n")
    
    # src/backtest/portfolio.py を確認
    portfolio_path = Path("src/backtest/portfolio.py")
    
    if portfolio_path.exists():
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # get_trades_dataframe メソッドを探す
        if "get_trades_dataframe" in content:
            print("✓ get_trades_dataframeメソッドが存在します")
            
            # メソッドの実装を確認
            lines = content.split('\n')
            in_method = False
            method_lines = []
            
            for line in lines:
                if "def get_trades_dataframe" in line:
                    in_method = True
                
                if in_method:
                    method_lines.append(line)
                    if line.strip() and not line.startswith(' ') and len(method_lines) > 1:
                        break
            
            if method_lines:
                print("\nメソッドの最初の部分:")
                print('\n'.join(method_lines[:10]))

if __name__ == "__main__":
    check_all_output_files()
    find_position_manager_output()
