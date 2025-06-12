#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
権利落ち日の隠れた買い増しを修正するスクリプト
"""

import shutil
from pathlib import Path
from datetime import datetime


def backup_engine_file():
    """engine.pyのバックアップを作成"""
    engine_path = Path("src/backtest/engine.py")
    backup_path = Path(f"src/backtest/engine.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if engine_path.exists():
        shutil.copy2(engine_path, backup_path)
        print(f"✓ バックアップを作成しました: {backup_path}")
        return True
    else:
        print(f"❌ engine.pyが見つかりません: {engine_path}")
        return False


def fix_engine_code():
    """engine.pyの買い増し処理を修正"""
    engine_path = Path("src/backtest/engine.py")
    
    if not engine_path.exists():
        print(f"❌ engine.pyが見つかりません: {engine_path}")
        return False
    
    # ファイル内容を読み込み
    with open(engine_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正対象のコードを検索
    old_code = """            # 買い増しシグナルをチェック（権利落ち日のみ）
            if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():"""
    
    new_code = """            # 買い増しシグナルをチェック（権利落ち日のみ）
            if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():"""
    
    if old_code in content:
        # コードを置換
        fixed_content = content.replace(old_code, new_code)
        
        # ファイルに書き戻し
        with open(engine_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✓ engine.pyを修正しました")
        print("\n【修正内容】")
        print("Before:")
        print(old_code)
        print("\nAfter:")
        print(new_code)
        return True
    else:
        print("⚠️ 修正対象のコードが見つかりません")
        print("手動で以下の修正を行ってください：")
        print("\n_process_existing_positions メソッド内の")
        print("if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():")
        print("\nを以下に変更：")
        print("if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():")
        return False


def verify_fix():
    """修正が正しく適用されたか確認"""
    engine_path = Path("src/backtest/engine.py")
    
    if not engine_path.exists():
        return False
    
    with open(engine_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正後のコードが存在するか確認
    expected_code = "if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():"
    
    if expected_code in content:
        print("\n✓ 修正が正しく適用されています")
        return True
    else:
        print("\n❌ 修正が適用されていません")
        return False


def main():
    """メイン処理"""
    print("=== 権利落ち日の隠れた買い増し修正 ===\n")
    
    # 1. バックアップ作成
    if not backup_engine_file():
        return
    
    # 2. 修正実行
    if fix_engine_code():
        # 3. 検証
        verify_fix()
        
        print("\n【次のステップ】")
        print("1. 修正が適用されたことを確認")
        print("2. バックテストを再実行して結果を確認")
        print("   python main.py --config config/minimal_debug.yaml")
        print("\n3. 問題が解決しない場合は、バックアップから復元：")
        print("   cp src/backtest/engine.py.backup_* src/backtest/engine.py")
    else:
        print("\n修正に失敗しました。手動での修正が必要です。")


if __name__ == "__main__":
    main()
