#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当支払い処理のデバッグ
なぜ配当収入が0円になるのかを調査
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timedelta
import pandas as pd
import json
from pathlib import Path


def check_dividend_payment_dates():
    """配当支払日の計算ロジックを確認"""
    print("=== 配当支払日の計算ロジック確認 ===\n")
    
    # engine.pyの計算ロジックを再現
    test_cases = [
        ("2023-04-03", "3月決算"),  # トヨタの権利確定日
        ("2023-10-02", "9月中間"),  # トヨタの中間配当
        ("2023-04-03", "3月決算"),  # ソニー
    ]
    
    for record_date_str, desc in test_cases:
        record_date = datetime.strptime(record_date_str, "%Y-%m-%d")
        
        # engine.pyのロジック
        if record_date.month == 3:
            payment_date = datetime(record_date.year, 6, 25)
        elif record_date.month == 9:
            payment_date = datetime(record_date.year, 12, 10)
        else:
            payment_date = record_date + timedelta(days=75)
        
        print(f"{desc}:")
        print(f"  権利確定日: {record_date.strftime('%Y-%m-%d')}")
        print(f"  支払予定日: {payment_date.strftime('%Y-%m-%d')}")
        print(f"  バックテスト期間内？: {'Yes' if payment_date.year <= 2023 else 'No'}")
        print()


def check_position_dividend_info():
    """ポジション情報の配当データを確認"""
    print("\n=== ポジション情報の配当データ確認 ===\n")
    
    # 最新のポジションファイルを探す
    results_dir = Path("data/results")
    position_files = sorted(results_dir.glob("positions_*.csv"))
    
    if position_files:
        latest_positions = position_files[-1]
        positions_df = pd.read_csv(latest_positions)
        
        print(f"分析対象: {latest_positions.name}\n")
        
        # 配当情報を持つポジションを確認
        print("【ポジションの配当情報】")
        print("ticker | entry_date | exit_date | dividend_received")
        print("-" * 60)
        
        for _, pos in positions_df.iterrows():
            if 'dividend_received' in pos:
                print(f"{pos['ticker']:6} | {pos['entry_date']:10} | {pos.get('exit_date', 'OPEN'):10} | {pos.get('dividend_received', 0):,.0f}")


def analyze_engine_dividend_process():
    """engine.pyの配当処理を詳細分析"""
    print("\n\n=== Engine.pyの配当処理分析 ===\n")
    
    # engine.pyの_process_dividends メソッドを確認
    engine_file = Path("src/backtest/engine.py")
    
    with open(engine_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 配当処理部分を探す
    if "_process_dividends" in content:
        print("✅ _process_dividends メソッドが存在")
        
        # 配当支払日の計算部分を抽出
        lines = content.split('\n')
        in_dividend_method = False
        for i, line in enumerate(lines):
            if "_process_dividends" in line:
                in_dividend_method = True
            elif in_dividend_method and "def " in line and "_process_dividends" not in line:
                break
            elif in_dividend_method and "payment_date" in line:
                print(f"行{i+1}: {line.strip()}")
    
    print("\n【問題の可能性】")
    print("1. 権利確定日の月判定が間違っている")
    print("   → record_date.month == 3 ではなく record_date.month == 4 の可能性")
    print("2. ポジションのrecord_dateが正しく設定されていない")
    print("3. 配当支払日がバックテスト期間外になっている")


def check_actual_dividend_payments():
    """実際の日本企業の配当支払日を確認"""
    print("\n\n=== 実際の配当支払日（参考）===\n")
    
    print("【一般的な日本企業の配当支払いスケジュール】")
    print("3月決算企業:")
    print("  - 権利確定日: 3月31日")
    print("  - 配当支払日: 6月下旬（株主総会後）")
    print("\n9月中間配当:")
    print("  - 権利確定日: 9月30日") 
    print("  - 配当支払日: 12月上旬")
    
    print("\n⚠️ 注意: 権利確定日の月は通常3月と9月だが、")
    print("    engine.pyでは4月と10月で判定している可能性")


def create_fix_suggestion():
    """修正案を生成"""
    print("\n\n=== 修正案 ===\n")
    
    fix_code = '''
# src/backtest/engine.py の _calculate_dividend_payment_date メソッドを修正

def _calculate_dividend_payment_date(self, record_date: datetime) -> datetime:
    """配当支払日を計算（修正版）"""
    # 権利確定日の月で判定（3月末、9月末が一般的）
    if record_date.month == 3 or record_date.month == 4:  # 3月決算
        # 6月下旬に支払い
        return datetime(record_date.year, 6, 25)
    elif record_date.month == 9 or record_date.month == 10:  # 中間配当
        # 12月上旬に支払い
        return datetime(record_date.year, 12, 10)
    else:
        # その他は2.5ヶ月後
        return record_date + timedelta(days=75)

# または、配当落ち日にすぐに配当を計上する簡易版
def _process_dividends(self, current_date: datetime) -> None:
    """配当処理（簡易版）"""
    positions = self.portfolio.position_manager.get_open_positions()
    
    for position in positions:
        # 配当落ち日に配当を計上
        if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
            if position.dividend_amount:
                # 税引後配当金を計算
                net_dividend_per_share = position.dividend_amount * (1 - self.execution_config.tax_rate)
                
                self.portfolio.update_dividend(
                    ticker=position.ticker,
                    dividend_per_share=net_dividend_per_share,
                    date=current_date
                )
'''
    print(fix_code)


def main():
    """メイン処理"""
    print("配当支払い処理のデバッグ")
    print("=" * 70)
    
    check_dividend_payment_dates()
    check_position_dividend_info()
    analyze_engine_dividend_process()
    check_actual_dividend_payments()
    create_fix_suggestion()
    
    print("\n\n=== まとめ ===")
    print("配当収入が0円になる原因:")
    print("1. 権利確定日が4月と10月で記録されているが、")
    print("   engine.pyは3月と9月で判定している")
    print("2. 結果として配当支払日が計算されず、配当が支払われない")
    print("\n解決策:")
    print("- 権利確定日の月判定を修正（3,4月と9,10月を含める）")
    print("- または配当落ち日に即座に配当を計上する")


if __name__ == "__main__":
    main()
