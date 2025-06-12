#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当情報の設定状況を詳しく確認
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime
import pandas as pd
from pathlib import Path


def check_data_manager_dividend():
    """DataManagerのget_next_dividendメソッドを確認"""
    print("=== DataManagerの配当取得メソッドを確認 ===\n")
    
    data_manager_file = Path("src/data/data_manager.py")
    
    with open(data_manager_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'get_next_dividend' in content:
        print("✅ get_next_dividendメソッドが存在")
        
        # メソッドの実装を確認
        lines = content.split('\n')
        in_method = False
        method_lines = []
        
        for line in lines:
            if 'def get_next_dividend' in line:
                in_method = True
            elif in_method and line.strip() and not line.startswith(' '):
                break
            
            if in_method:
                method_lines.append(line)
        
        if method_lines:
            print("\n【メソッドの実装】")
            for line in method_lines[:20]:  # 最初の20行
                print(line)
    else:
        print("❌ get_next_dividendメソッドが見つかりません")


def check_position_manager_dividend():
    """PositionManagerでの配当情報設定を確認"""
    print("\n\n=== PositionManagerの配当情報設定を確認 ===\n")
    
    position_manager_file = Path("src/strategy/position_manager.py")
    
    with open(position_manager_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # open_positionメソッドでの配当情報設定を確認
    if 'position.dividend_amount = dividend_info.get' in content:
        print("✅ ポジション作成時に配当情報が設定されています")
    else:
        print("❌ 配当情報の設定が見つかりません")
    
    # Positionクラスの属性を確認
    print("\n【Positionクラスの配当関連属性】")
    attributes = ['ex_dividend_date', 'record_date', 'dividend_amount', 'dividend_received']
    
    for attr in attributes:
        if f'{attr}:' in content or f'{attr} =' in content:
            print(f"✅ {attr}")
        else:
            print(f"❌ {attr}")


def add_debug_logging():
    """デバッグログを追加するコード例"""
    print("\n\n=== デバッグログの追加案 ===\n")
    
    print("【engine.pyの_check_new_entries内】")
    print("```python")
    print("dividend_info = self.data_manager.get_next_dividend(ticker, current_date)")
    print("if dividend_info:")
    print("    log.debug(f'{ticker}: 配当情報取得 - 権利落ち日={dividend_info.get(\"ex_dividend_date\")}, 金額={dividend_info.get(\"dividend_amount\")}')")
    print("```")
    
    print("\n【position_manager.pyのopen_position内】")
    print("```python")
    print("if dividend_info:")
    print("    position.ex_dividend_date = dividend_info.get('ex_dividend_date')")
    print("    position.record_date = dividend_info.get('record_date')")
    print("    position.dividend_amount = dividend_info.get('dividend_amount')")
    print("    log.debug(f'{ticker}: ポジションに配当情報設定 - 金額={position.dividend_amount}')")
    print("```")
    
    print("\n【engine.pyの_process_dividends内】")
    print("```python")
    print("for position in positions:")
    print("    log.debug(f'{position.ticker}: 配当チェック - ex_date={position.ex_dividend_date}, amount={position.dividend_amount}')")
    print("```")


def check_test_results():
    """最新のテスト結果から配当情報を確認"""
    print("\n\n=== 最新のテスト結果を確認 ===\n")
    
    results_dir = Path("data/results/test_fixed")
    if not results_dir.exists():
        print("テスト結果ディレクトリが見つかりません")
        return
    
    # 最新のポジションファイルを探す
    position_files = sorted(results_dir.glob("positions_*.csv"))
    if position_files:
        latest = position_files[-1]
        print(f"分析対象: {latest.name}")
        
        df = pd.read_csv(latest)
        print("\n【ポジションの配当情報】")
        print(df[['ticker', 'entry_date', 'exit_date', 'dividend_received']].to_string(index=False))


def main():
    """メイン処理"""
    print("配当情報の設定状況を詳しく確認")
    print("=" * 70)
    
    check_data_manager_dividend()
    check_position_manager_dividend()
    add_debug_logging()
    check_test_results()
    
    print("\n\n=== 推奨される次のステップ ===")
    print("1. fix_dividend_immediate.pyを実行して配当処理を修正")
    print("2. デバッグレベルでバックテストを実行:")
    print("   python main.py --config config/test_fixed.yaml")
    print("3. ログで配当情報の流れを確認")


if __name__ == "__main__":
    main()
