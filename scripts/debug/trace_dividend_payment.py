#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当支払いがなぜ実行されないかを詳細に調査
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from src.utils.calendar import DividendDateCalculator


def trace_dividend_flow():
    """配当処理のフローを追跡"""
    print("=== 配当処理フローの追跡 ===\n")
    
    # トヨタの2023年3月の例
    ticker = "7203"
    yf_ticker = yf.Ticker(f"{ticker}.T")
    
    # 配当データ取得
    dividends = yf_ticker.dividends['2023-01-01':'2023-12-31']
    
    for ex_date, amount in dividends.items():
        print(f"\n【{ticker} - 権利落ち日: {ex_date.strftime('%Y-%m-%d')}】")
        print(f"配当金額: {amount:.2f}円")
        
        # 権利確定日を計算
        record_date = DividendDateCalculator.calculate_record_date(ex_date.to_pydatetime())
        print(f"権利確定日: {record_date.strftime('%Y-%m-%d')}")
        
        # 配当支払日を計算（engine.pyのロジック）
        if record_date.month in [3, 4]:
            payment_date = datetime(record_date.year, 6, 25)
        elif record_date.month in [9, 10]:
            payment_date = datetime(record_date.year, 12, 10)
        else:
            payment_date = record_date + timedelta(days=75)
        
        print(f"配当支払日（計算）: {payment_date.strftime('%Y-%m-%d')}")
        
        # バックテスト期間内かチェック
        if payment_date > datetime(2023, 12, 31):
            print("⚠️ 配当支払日がバックテスト期間外！")
        else:
            print("✅ 配当支払日はバックテスト期間内")


def analyze_position_dividend_info():
    """ポジション作成時の配当情報を分析"""
    print("\n\n=== ポジション作成時の配当情報 ===\n")
    
    # ポジションCSVから実際の取引を確認
    positions = [
        {"ticker": "7203", "entry": "2023-03-29", "exit": "2023-04-03"},
        {"ticker": "7203", "entry": "2023-09-27", "exit": "2023-10-04"},
    ]
    
    for pos in positions:
        ticker = pos["ticker"]
        entry_date = datetime.strptime(pos["entry"], "%Y-%m-%d")
        exit_date = datetime.strptime(pos["exit"], "%Y-%m-%d")
        
        print(f"\n【{ticker}】")
        print(f"エントリー: {entry_date.strftime('%Y-%m-%d')}")
        print(f"決済: {exit_date.strftime('%Y-%m-%d')}")
        
        # この期間の配当を確認
        yf_ticker = yf.Ticker(f"{ticker}.T")
        dividends = yf_ticker.dividends[entry_date:exit_date + timedelta(days=90)]
        
        if dividends.empty:
            print("⚠️ この期間に配当データなし")
        else:
            for ex_date, amount in dividends.items():
                print(f"  権利落ち日: {ex_date.strftime('%Y-%m-%d')}, 金額: {amount:.2f}円")


def check_portfolio_update_dividend():
    """Portfolio.update_dividendが呼ばれているか確認"""
    print("\n\n=== update_dividendメソッドの呼び出し確認 ===\n")
    
    # engine.pyの_process_dividendsメソッドを確認
    print("【engine.pyの配当処理】")
    print("1. ポジションのrecord_dateをチェック")
    print("2. 配当支払日を計算")
    print("3. 現在日が配当支払日かチェック")
    print("4. portfolio.update_dividendを呼び出し")
    
    print("\n【問題の可能性】")
    print("- position.record_dateがNoneになっている？")
    print("- position.dividend_amountがNoneになっている？")
    print("- 配当支払日の計算が間違っている？")


def check_position_creation():
    """ポジション作成時の配当情報設定を確認"""
    print("\n\n=== ポジション作成時の配当情報設定 ===\n")
    
    print("【position_manager.pyのopen_position】")
    print("配当情報の設定箇所:")
    print("```python")
    print("if dividend_info:")
    print("    position.ex_dividend_date = dividend_info.get('ex_dividend_date')")
    print("    position.record_date = dividend_info.get('record_date')")
    print("    position.dividend_amount = dividend_info.get('dividend_amount')")
    print("```")
    
    print("\n【確認ポイント】")
    print("1. dividend_infoが正しく渡されているか")
    print("2. get_next_dividendが正しい配当情報を返しているか")


def suggest_immediate_fix():
    """即座に適用できる修正案"""
    print("\n\n=== 即座に適用できる修正案 ===\n")
    
    print("【案1: 配当支払日を権利落ち日の1ヶ月後に簡略化】")
    print("```python")
    print("def _calculate_dividend_payment_date(self, record_date: datetime) -> datetime:")
    print("    # 簡略化: 権利確定日の1ヶ月後")
    print("    return record_date + timedelta(days=30)")
    print("```")
    
    print("\n【案2: 権利落ち日に即座に配当を計上】")
    print("```python")
    print("def _process_dividends(self, current_date: datetime) -> None:")
    print("    positions = self.portfolio.position_manager.get_open_positions()")
    print("    ")
    print("    for position in positions:")
    print("        # 権利落ち日に配当を計上")
    print("        if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():")
    print("            if position.dividend_amount:")
    print("                net_dividend_per_share = position.dividend_amount * (1 - self.execution_config.tax_rate)")
    print("                self.portfolio.update_dividend(")
    print("                    ticker=position.ticker,")
    print("                    dividend_per_share=net_dividend_per_share,")
    print("                    date=current_date")
    print("                )")
    print("```")


def main():
    """メイン処理"""
    print("配当支払い問題の詳細調査")
    print("=" * 70)
    
    trace_dividend_flow()
    analyze_position_dividend_info()
    check_portfolio_update_dividend()
    check_position_creation()
    suggest_immediate_fix()
    
    print("\n\n=== 結論 ===")
    print("配当が支払われない最も可能性の高い原因:")
    print("1. 権利確定日が4月と10月になっているため、")
    print("   6月と12月の配当支払日がバックテスト期間内に入らない")
    print("2. 特に9月のポジションは10月26日に決済されるが、")
    print("   配当支払日は12月10日のため、配当を受け取れない")
    print("\n推奨:")
    print("- 権利落ち日または権利確定日の1ヶ月後に配当を計上する")
    print("- または、配当を即座に計上する簡略化版を採用する")


if __name__ == "__main__":
    main()
