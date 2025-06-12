#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細なデバッグ - コードの状態と実行時の動作を確認
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
from datetime import datetime


def check_current_code_state():
    """現在のコードの状態を確認"""
    print("=== 現在のコードの状態確認 ===\n")
    
    # engine.pyの内容を確認
    engine_path = Path("src/backtest/engine.py")
    with open(engine_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 買い増し処理の部分を探す
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'ex_dividend_date' in line and 'current_date.date()' in line:
            print(f"Line {i+1}: {line.strip()}")
            # 前後の行も表示
            for j in range(max(0, i-2), min(len(lines), i+3)):
                print(f"  {j+1}: {lines[j]}")
            print()
    
    # portfolio.pyの内容も確認
    portfolio_path = Path("src/backtest/portfolio.py")
    with open(portfolio_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # execute_buyメソッドの重要部分を探す
    if 'if reason and ("Add" in reason or "add" in reason):' in content:
        print("✓ portfolio.pyは修正済みです（買い増しチェックあり）")
    else:
        print("⚠️ portfolio.pyの修正が見つかりません")


def analyze_latest_results():
    """最新のバックテスト結果を分析"""
    print("\n\n=== 最新のバックテスト結果分析 ===\n")
    
    # 最新の取引履歴を探す
    results_dir = Path("data/results/minimal_debug")
    trade_files = sorted(results_dir.glob("trades_*.csv"), reverse=True)
    
    if trade_files:
        latest_trades = trade_files[0]
        print(f"最新の取引履歴: {latest_trades}")
        
        trades_df = pd.read_csv(latest_trades)
        print("\n取引履歴:")
        print(trades_df.to_string(index=False))
        
        # BUY取引が複数あるかチェック
        buy_trades = trades_df[trades_df['type'] == 'BUY']
        if len(buy_trades) > 1:
            print(f"\n⚠️ BUY取引が{len(buy_trades)}回実行されています！")
            for _, trade in buy_trades.iterrows():
                print(f"  {trade['date']}: {trade['shares']}株 理由: {trade['reason']}")
        else:
            print(f"\n✓ BUY取引は1回のみ: {len(buy_trades)}回")
    
    # 最新のポジション履歴も確認
    position_files = sorted(results_dir.glob("positions_*.csv"), reverse=True)
    if position_files:
        latest_positions = position_files[0]
        positions_df = pd.read_csv(latest_positions)
        print(f"\n\nポジション履歴:")
        print(positions_df.to_string(index=False))


def trace_execution_with_logging():
    """実行時のログを詳細に追跡"""
    print("\n\n=== 実行時ログの追跡 ===\n")
    
    # 最新のログファイルを確認
    log_path = Path("logs/minimal_debug.log")
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 最後の実行セッションのログを抽出
        print("最新セッションの重要なログ:")
        session_start = False
        for line in lines:
            if "Loading configuration from: config/minimal_debug.yaml" in line:
                session_start = True
            
            if session_start:
                # 重要なログを抽出
                if any(keyword in line for keyword in [
                    "Buy executed", "Sell executed", "Position already exists",
                    "add_to_position", "open_position", "total_shares"
                ]):
                    print(line.strip())


def check_cache_data():
    """キャッシュされているデータを確認"""
    print("\n\n=== キャッシュデータの確認 ===\n")
    
    cache_dir = Path("data/cache_minimal")
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.pkl"))
        print(f"キャッシュファイル数: {len(cache_files)}")
        
        # キャッシュをクリアする提案
        if cache_files:
            print("\nキャッシュが原因の可能性があります。")
            print("以下のコマンドでキャッシュをクリアしてください:")
            print("rm -rf data/cache_minimal/*")
            print("または")
            print("del /s /q data\\cache_minimal\\*")


def suggest_debug_modifications():
    """デバッグのための修正提案"""
    print("\n\n=== デバッグ修正の提案 ===\n")
    
    print("以下の修正を一時的に適用して問題を特定してください：")
    
    print("\n1. position_manager.pyにデバッグログを追加:")
    print("""
    def add_to_position(self, ...):
        # デバッグログを追加
        log.error(f"[DEBUG] add_to_position called for {ticker}: adding {shares} shares")
        log.error(f"[DEBUG] Current shares: {self.positions[ticker].total_shares}")
        
        # 既存のコード...
    """)
    
    print("\n2. engine.pyの_execute_entryにデバッグログを追加:")
    print("""
    def _execute_entry(self, signal, ...):
        # デバッグログを追加
        log.error(f"[DEBUG] _execute_entry called: {signal.ticker} {signal.signal_type.value} {signal.shares}株")
        
        # 既存のコード...
    """)


def main():
    """メイン処理"""
    check_current_code_state()
    analyze_latest_results()
    trace_execution_with_logging()
    check_cache_data()
    suggest_debug_modifications()
    
    print("\n\n=== 分析完了 ===")
    print("上記の情報から問題の原因を特定してください。")


if __name__ == "__main__":
    main()
