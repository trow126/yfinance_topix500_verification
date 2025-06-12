#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
買い増し機能の動作を検証するテストスクリプト
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config
from src.strategy.dividend_strategy import DividendStrategy
from datetime import datetime


def test_addition_enabled_check():
    """買い増し機能の有効/無効が正しく動作するかテスト"""
    print("=== 買い増し機能の動作テスト ===\n")
    
    # テスト用の設定を準備
    test_configs = [
        ("config/minimal_debug.yaml", False),  # 買い増し無効
        ("config/config.yaml", True),          # 買い増し有効（デフォルト設定）
    ]
    
    for config_path, expected_enabled in test_configs:
        print(f"\n【テスト】設定ファイル: {config_path}")
        
        try:
            # 設定を読み込み
            config = load_config(config_path)
            
            # 買い増し設定を確認
            addition_enabled = config.strategy.addition.enabled
            print(f"addition.enabled = {addition_enabled}")
            print(f"期待値: {expected_enabled}")
            
            # 戦略を初期化
            strategy = DividendStrategy(config.strategy)
            
            # テスト用のデータ
            position_info = {
                'entry_date': datetime(2023, 3, 28),
                'entry_price': 1850.0,
                'average_price': 1850.0,
                'total_shares': 500,
                'initial_value': 925000.0,
                'ex_dividend_date': datetime(2023, 3, 30),
                'pre_ex_price': 1880.0
            }
            
            # 買い増しシグナルをチェック
            add_signal = strategy.check_addition_signal(
                ticker="7203",
                current_date=datetime(2023, 3, 30),  # 権利落ち日
                position_info=position_info,
                current_price=1840.0,  # 下落している
                pre_ex_price=1880.0
            )
            
            # 結果を確認
            if addition_enabled and add_signal:
                print("✓ 買い増しシグナルが生成されました（正常）")
                print(f"  理由: {add_signal.reason}")
                print(f"  株数: {add_signal.shares}")
            elif not addition_enabled and not add_signal:
                print("✓ 買い増しシグナルが生成されませんでした（正常）")
            else:
                print("❌ 予期しない動作です！")
                if add_signal:
                    print(f"  買い増しが無効なのにシグナルが生成されました")
                else:
                    print(f"  買い増しが有効なのにシグナルが生成されませんでした")
            
        except Exception as e:
            print(f"❌ エラー: {e}")


def test_engine_addition_check():
    """engine.pyの買い増し条件チェックをテスト"""
    print("\n\n=== engine.pyの買い増し条件チェック ===\n")
    
    # engine.pyの内容を確認
    engine_path = Path("src/backtest/engine.py")
    
    if not engine_path.exists():
        print("❌ engine.pyが見つかりません")
        return
    
    with open(engine_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正前のパターン
    old_pattern = "if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():"
    
    # 修正後のパターン
    new_pattern = "if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():"
    
    if new_pattern in content:
        print("✓ engine.pyは修正済みです")
        print("  買い増し設定のチェックが含まれています")
    elif old_pattern in content:
        print("⚠️ engine.pyは未修正です")
        print("  買い増し設定のチェックが含まれていません")
        print("\n  fix_hidden_addition.py を実行して修正してください：")
        print("  python fix_hidden_addition.py")
    else:
        print("？ engine.pyの買い増し処理が見つかりません")
        print("  コードが変更されている可能性があります")


def main():
    """メイン処理"""
    test_addition_enabled_check()
    test_engine_addition_check()
    
    print("\n\n=== テスト完了 ===")
    print("買い増し機能が正しく動作することを確認してください。")


if __name__ == "__main__":
    main()
