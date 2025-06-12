#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窓埋め判定ロジックのデバッグ
権利落ち前価格がなぜ低く設定されるのかを調査
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime
import pandas as pd
import yfinance as yf
from src.utils.calendar import BusinessDayCalculator


def analyze_pre_ex_price_logic():
    """権利落ち前価格の設定ロジックを分析"""
    print("=== 権利落ち前価格の設定ロジック分析 ===\n")
    
    # トヨタの2023年3月の例
    ticker = yf.Ticker("7203.T")
    
    # エントリー日から権利落ち日までのデータ
    hist = ticker.history(start="2023-03-25", end="2023-04-01", auto_adjust=False)
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    
    print("【トヨタ - 2023年3月】")
    print("日付         | 終値")
    print("-" * 30)
    for date, row in hist.iterrows():
        print(f"{date.strftime('%Y-%m-%d')} | {row['Close']:,.2f}")
        if row.get('Dividends', 0) > 0:
            print(f"            ↑ 配当落ち日（配当: {row['Dividends']:.2f}円）")
    
    print("\n【問題の分析】")
    
    # 権利落ち日を特定
    ex_date = None
    for date, row in hist.iterrows():
        if row.get('Dividends', 0) > 0:
            ex_date = date
            break
    
    if ex_date:
        # 権利落ち前日を計算
        pre_ex_date = BusinessDayCalculator.add_business_days(ex_date, -1)
        print(f"権利落ち日: {ex_date.strftime('%Y-%m-%d')}")
        print(f"権利落ち前日（計算）: {pre_ex_date.strftime('%Y-%m-%d')}")
        
        # 実際の前日の価格
        actual_dates = hist.index.tolist()
        ex_date_idx = actual_dates.index(ex_date)
        if ex_date_idx > 0:
            actual_pre_ex_date = actual_dates[ex_date_idx - 1]
            actual_pre_ex_price = hist.loc[actual_pre_ex_date, 'Close']
            print(f"権利落ち前日（実際）: {actual_pre_ex_date.strftime('%Y-%m-%d')}")
            print(f"権利落ち前日価格: {actual_pre_ex_price:,.2f}円")


def check_entry_timing():
    """エントリータイミングと価格の関係を確認"""
    print("\n\n=== エントリータイミングの確認 ===\n")
    
    # 戦略設定
    days_before_record = 3  # 権利確定日の3営業日前
    
    # 2023年3月の例
    record_date = datetime(2023, 4, 3)  # 権利確定日（月曜日）
    ex_date = datetime(2023, 3, 30)     # 権利落ち日（木曜日）
    
    # エントリー日を計算
    # 権利確定日の3営業日前
    entry_date = BusinessDayCalculator.add_business_days(record_date, -days_before_record)
    
    print(f"権利確定日: {record_date.strftime('%Y-%m-%d (%a)')}")
    print(f"権利落ち日: {ex_date.strftime('%Y-%m-%d (%a)')}")
    print(f"エントリー日: {entry_date.strftime('%Y-%m-%d (%a)')}")
    
    # 権利落ち前日
    pre_ex_date = BusinessDayCalculator.add_business_days(ex_date, -1)
    print(f"権利落ち前日: {pre_ex_date.strftime('%Y-%m-%d (%a)')}")
    
    print("\n【タイミングの問題】")
    if entry_date >= pre_ex_date:
        print("⚠️ エントリー日が権利落ち前日以降！")
        print("   → 権利落ち前価格がエントリー価格より低くなる可能性")
    else:
        print("✅ エントリー日は権利落ち前日より前")


def simulate_correct_window_fill():
    """正しい窓埋め判定のシミュレーション"""
    print("\n\n=== 正しい窓埋め判定のシミュレーション ===\n")
    
    # トヨタの実際のデータでシミュレーション
    ticker = yf.Ticker("7203.T")
    hist = ticker.history(start="2023-03-20", end="2023-04-10", auto_adjust=False)
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    
    # 権利落ち日を見つける
    ex_date = None
    for date, row in hist.iterrows():
        if row.get('Dividends', 0) > 0:
            ex_date = date
            break
    
    if ex_date:
        # 権利落ち前日の価格（実際のデータから）
        dates_list = hist.index.tolist()
        ex_idx = dates_list.index(ex_date)
        pre_ex_price = hist.iloc[ex_idx - 1]['Close']
        
        print(f"権利落ち前日価格: {pre_ex_price:,.2f}円")
        print(f"権利落ち日価格: {hist.loc[ex_date, 'Close']:,.2f}円")
        print(f"配当金額: {hist.loc[ex_date, 'Dividends']:,.2f}円")
        
        print("\n【その後の価格推移と窓埋め判定】")
        print("日付         | 終値      | 窓埋め？")
        print("-" * 40)
        
        for i in range(ex_idx, min(ex_idx + 10, len(hist))):
            date = dates_list[i]
            price = hist.iloc[i]['Close']
            filled = "○" if price >= pre_ex_price else "×"
            print(f"{date.strftime('%Y-%m-%d')} | {price:8,.2f} | {filled}")


def suggest_fixes():
    """修正案の提示"""
    print("\n\n=== 修正案 ===\n")
    
    print("【1. 権利落ち前価格の正しい取得】")
    print("```python")
    print("# engine.py の _process_existing_positions メソッド内")
    print("# 権利落ち日の処理で、前日価格を正しく取得")
    print("if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():")
    print("    # データから実際の前営業日を取得")
    print("    price_data = self.data_manager.get_price_data(ticker)")
    print("    dates = price_data.index.tolist()")
    print("    current_idx = dates.index(current_date)")
    print("    if current_idx > 0:")
    print("        pre_ex_price = price_data.iloc[current_idx - 1]['Close']")
    print("```")
    
    print("\n【2. エントリータイミングの調整】")
    print("権利確定日の3営業日前ではなく、")
    print("権利落ち日の2営業日前にエントリーする方が安全")
    
    print("\n【3. 窓埋め判定の改善】")
    print("- 最低保有期間を設定（例：3営業日）")
    print("- 配当落ち幅を考慮した判定")


def main():
    """メイン処理"""
    print("窓埋め判定ロジックのデバッグ")
    print("=" * 70)
    
    analyze_pre_ex_price_logic()
    check_entry_timing()
    simulate_correct_window_fill()
    suggest_fixes()
    
    print("\n\n=== まとめ ===")
    print("権利落ち前価格が低く設定される原因:")
    print("1. BusinessDayCalculatorで計算した日付と")
    print("   実際の取引日がずれている可能性")
    print("2. エントリータイミングが遅すぎる可能性")
    print("3. 価格データの取得方法に問題がある可能性")


if __name__ == "__main__":
    main()
