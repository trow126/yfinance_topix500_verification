#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
売却株数が2倍になる原因を特定するデバッグスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path


def check_trade_count_issue():
    """trade_countと株数の関係を確認"""
    print("=== trade_countと株数の関係を確認 ===\n")
    
    # positionsファイルを確認
    positions_file = Path("data/results/simple/positions_20250612_125740.csv")
    
    if positions_file.exists():
        import pandas as pd
        positions_df = pd.read_csv(positions_file)
        
        print("【ポジション詳細】")
        print("ticker | total_shares | trade_count | average_price")
        print("-" * 50)
        
        for _, pos in positions_df.iterrows():
            print(f"{pos['ticker']:6} | {pos['total_shares']:12} | {pos['trade_count']:11} | {pos['average_price']:.2f}")
        
        print("\n⚠️ 注意: total_sharesが0になっているのは、売却後の値")
        print("⚠️ trade_countが2になっているのは、買い1回+売り1回の合計")


def analyze_position_manager_bug():
    """PositionManagerのバグの可能性を分析"""
    print("\n\n=== PositionManagerのバグ分析 ===\n")
    
    print("【仮説1】trade_countを株数倍率として使っている？")
    print("  → trade_count = 2（買い+売り）")
    print("  → 売却株数 = 保有株数 × trade_count ?")
    print("  → 500株 × 2 = 1000株")
    
    print("\n【仮説2】どこかで買い増しが隠れて実行されている？")
    print("  → しかし取引履歴にAddの記録なし")
    print("  → ログにも買い増しの記録なし")
    
    print("\n【仮説3】売却時の株数取得にバグ？")
    print("  → position.total_sharesが正しく取得できていない")
    print("  → または別の値が参照されている")


def create_fix_patch():
    """修正パッチの提案"""
    print("\n\n=== 修正パッチの提案 ===\n")
    
    fix_code = '''
# src/strategy/dividend_strategy.py の check_exit_signal メソッドを修正

def check_exit_signal(self, ticker, current_date, position_info, current_price):
    """決済シグナルをチェック（修正版）"""
    entry_date = position_info['entry_date']
    entry_price = position_info['entry_price']
    avg_price = position_info['average_price']
    total_shares = position_info['total_shares']  # ← ここが重要
    
    # デバッグ出力を追加
    log.debug(f"{ticker}: 決済チェック - 保有株数={total_shares}")
    
    # ... 省略 ...
    
    # 決済シグナルを生成
    if exit_reason != ExitReason.NONE:
        # 株数が正しいか確認
        if total_shares <= 0:
            log.error(f"{ticker}: 異常な株数 {total_shares}")
            return None
            
        return Signal(
            ticker=ticker,
            signal_type=SignalType.EXIT,
            date=current_date,
            price=current_price,
            shares=total_shares,  # ← ここで正しい株数を使用
            reason=reason_text,
            metadata={...}
        )
'''
    print(fix_code)


def check_engine_bug():
    """engine.pyのバグの可能性を確認"""
    print("\n\n=== engine.pyのバグチェック ===\n")
    
    print("【確認ポイント】")
    print("1. _process_existing_positions内でのposition_info作成")
    print("2. total_sharesの値が正しく渡されているか")
    print("3. 買い増し処理が本当に無効化されているか")
    
    print("\n【デバッグ案】")
    print("engine.py の _process_existing_positions に以下を追加：")
    print("""
# ポジション情報を作成する前に
log.info(f"{ticker}: ポジション情報 - 実際の株数={position.total_shares}")

# position_info作成後に
log.info(f"{ticker}: position_info - 株数={position_info['total_shares']}")
""")


def suggest_immediate_fix():
    """即効性のある修正案"""
    print("\n\n=== 即効性のある修正案 ===\n")
    
    print("1. **買い増し機能を有効化する**")
    print("   - 本来の戦略コンセプトに合わせる")
    print("   - addition.enabled: true に変更")
    print("   - ただし、これだけでは売却株数2倍問題は解決しない")
    
    print("\n2. **売却株数を明示的に制限**")
    print("   - portfolio.pyのexecute_sellで株数チェック")
    print("   - position.total_shares以上は売却不可")
    
    print("\n3. **最小限の修正で確認**")
    print("   - まず1銘柄、短期間でテスト")
    print("   - ログレベルをDEBUGにして詳細確認")


if __name__ == "__main__":
    check_trade_count_issue()
    analyze_position_manager_bug()
    create_fix_patch()
    check_engine_bug()
    suggest_immediate_fix()
