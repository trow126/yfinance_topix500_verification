#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
株数変更の追跡 - どこで500株が1000株になるか特定
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config
from src.backtest.engine import BacktestEngine
from src.utils.logger import log, BacktestLogger
from src.strategy.position_manager import Position
import pandas as pd


# Positionクラスをモンキーパッチして株数変更を追跡
original_setattr = Position.__setattr__

def traced_setattr(self, name, value):
    if name == 'total_shares' and hasattr(self, 'ticker'):
        current_value = getattr(self, name, None)
        if current_value is not None and current_value != value:
            log.error(f"[TRACE] {self.ticker}: total_shares変更 {current_value} → {value}")
            import traceback
            traceback.print_stack()
    original_setattr(self, name, value)

Position.__setattr__ = traced_setattr


def run_traced_backtest():
    """トレース付きでバックテストを実行"""
    print("=== 株数変更の追跡バックテスト ===\n")
    
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
    
    print("取引日ごとに処理を追跡します...\n")
    
    # 各日の処理前後でポジションを確認
    for i, current_date in enumerate(engine.trading_days):
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 現在の価格を取得
        current_prices = engine._get_current_prices(current_date.to_pydatetime())
        
        # 処理前のポジション確認
        positions_before = engine.portfolio.position_manager.get_open_positions()
        if positions_before:
            for pos in positions_before:
                log.info(f"[{date_str}] 処理前: {pos.ticker} = {pos.total_shares}株")
        
        # 日次処理を実行
        engine._process_day(current_date.to_pydatetime())
        
        # 処理後のポジション確認
        positions_after = engine.portfolio.position_manager.get_open_positions()
        if positions_after:
            for pos in positions_after:
                log.info(f"[{date_str}] 処理後: {pos.ticker} = {pos.total_shares}株")
    
    # 結果を生成
    results = engine._generate_results()
    
    print("\n\n=== バックテスト完了 ===")
    print("上記のログで株数が変更された箇所を確認してください。")
    
    return results


def check_position_object_manipulation():
    """Positionオブジェクトの直接操作をチェック"""
    print("\n\n=== コード内のtotal_shares直接操作をチェック ===\n")
    
    # srcディレクトリ内のすべてのPythonファイルを検索
    src_path = Path("src")
    for py_file in src_path.rglob("*.py"):
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # total_sharesへの直接代入を探す
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'total_shares' in line and '=' in line and 'self.total_shares' not in line:
                # 代入文の可能性がある
                if '.total_shares' in line and '==' not in line and '!=' not in line:
                    print(f"{py_file}:{i+1}: {line.strip()}")


def analyze_position_class():
    """Positionクラスの構造を分析"""
    print("\n\n=== Positionクラスの分析 ===\n")
    
    # position_manager.pyの内容を確認
    with open("src/strategy/position_manager.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # total_sharesを変更する箇所を探す
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'self.total_shares' in line and ('=' in line or '+=' in line or '-=' in line):
            print(f"Line {i+1}: {line.strip()}")
            # 前後の文脈も表示
            for j in range(max(0, i-2), min(len(lines), i+3)):
                if j != i:
                    print(f"  {j+1}: {lines[j]}")
            print()


def main():
    """メイン処理"""
    # コード分析
    check_position_object_manipulation()
    analyze_position_class()
    
    # トレース付きバックテスト実行
    print("\n" + "="*60)
    input("Enterキーを押してトレース付きバックテストを開始...")
    run_traced_backtest()


if __name__ == "__main__":
    main()
