#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細なデバッグスクリプト - 隠れた買い増し問題の原因を特定
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config
from src.backtest.engine import BacktestEngine
from src.utils.logger import log, BacktestLogger
import pandas as pd


def trace_position_changes():
    """ポジションの変化を詳細に追跡"""
    print("=== ポジション変化の詳細追跡 ===\n")
    
    # デバッグレベルのロギング設定
    logger = BacktestLogger()
    logger.setup_logger(log_level="DEBUG")
    
    # 設定読み込み
    config_path = "config/minimal_debug.yaml"
    config = load_config(config_path)
    
    # バックテストエンジンを初期化
    engine = BacktestEngine(config)
    
    # データをロード
    engine._load_data()
    
    # 取引日ごとに詳細に処理を追跡
    position_history = []
    
    for i, current_date in enumerate(engine.trading_days):
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 現在の価格を取得
        current_prices = engine._get_current_prices(current_date.to_pydatetime())
        
        # ポジション状態を記録
        positions = engine.portfolio.position_manager.get_open_positions()
        for pos in positions:
            position_info = {
                'date': date_str,
                'ticker': pos.ticker,
                'total_shares': pos.total_shares,
                'average_price': pos.average_price,
                'trades_count': len(pos.trades),
                'ex_dividend_date': pos.ex_dividend_date.strftime('%Y-%m-%d') if pos.ex_dividend_date else None
            }
            position_history.append(position_info)
            
            # 権利落ち日の処理を詳細に追跡
            if pos.ex_dividend_date and current_date.date() == pos.ex_dividend_date.date():
                print(f"\n[{date_str}] 権利落ち日の処理:")
                print(f"  銘柄: {pos.ticker}")
                print(f"  株数（処理前）: {pos.total_shares}")
                print(f"  config.strategy.addition.enabled = {config.strategy.addition.enabled}")
        
        # 日次処理を実行
        engine._process_day(current_date.to_pydatetime())
        
        # ポジション状態の変化を確認
        positions_after = engine.portfolio.position_manager.get_open_positions()
        for pos in positions_after:
            if any(p['ticker'] == pos.ticker and p['date'] == date_str for p in position_history):
                prev = next(p for p in position_history if p['ticker'] == pos.ticker and p['date'] == date_str)
                if prev['total_shares'] != pos.total_shares:
                    print(f"\n⚠️ [{date_str}] 株数が変化しました！")
                    print(f"  銘柄: {pos.ticker}")
                    print(f"  変更前: {prev['total_shares']}株")
                    print(f"  変更後: {pos.total_shares}株")
                    print(f"  取引数: {prev['trades_count']} → {len(pos.trades)}")
    
    # ポジション履歴をDataFrameで表示
    if position_history:
        df = pd.DataFrame(position_history)
        print("\n\nポジション履歴:")
        print(df.to_string(index=False))


def check_portfolio_execute_buy():
    """portfolio.execute_buyの動作を確認"""
    print("\n\n=== portfolio.execute_buyの動作確認 ===\n")
    
    with open("src/backtest/portfolio.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # execute_buyメソッドの重要部分を抽出
    if "if self.position_manager.get_position(ticker):" in content:
        print("portfolio.execute_buy内の分岐:")
        print("- 既存ポジションがある場合 → add_to_position が呼ばれる")
        print("- 新規ポジションの場合 → open_position が呼ばれる")
        print("\n⚠️ これが問題の可能性があります！")
        print("権利落ち日に何らかの理由でexecute_buyが呼ばれると、")
        print("既存ポジションに自動的に追加されてしまいます。")


def analyze_signal_generation():
    """シグナル生成の分析"""
    print("\n\n=== シグナル生成の分析 ===\n")
    
    # 設定読み込み
    config = load_config("config/minimal_debug.yaml")
    
    # 戦略設定を表示
    print("戦略設定:")
    print(f"  addition.enabled: {config.strategy.addition.enabled}")
    print(f"  addition.add_ratio: {config.strategy.addition.add_ratio}")
    print(f"  addition.add_on_drop: {config.strategy.addition.add_on_drop}")
    
    # dividend_strategy.pyの分析
    with open("src/strategy/dividend_strategy.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # check_addition_signalメソッドを確認
    if "def check_addition_signal" in content:
        print("\n✓ dividend_strategy.pyにcheck_addition_signalメソッドが存在")
        
        # enabledチェックを確認
        if "if not self.addition_config.enabled:" in content:
            print("✓ check_addition_signal内でenabledチェックが行われています")
        else:
            print("⚠️ check_addition_signal内でenabledチェックが見つかりません！")


def main():
    """メイン処理"""
    trace_position_changes()
    check_portfolio_execute_buy()
    analyze_signal_generation()
    
    print("\n\n=== 分析完了 ===")
    print("問題の原因を特定するため、上記の情報を確認してください。")


if __name__ == "__main__":
    main()
