#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当データ問題のデバッグスクリプト
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.calendar import DividendDateCalculator


def check_dividend_data():
    """各銘柄の配当データを確認"""
    print("=== 配当データ確認 ===\n")
    
    tickers = ["7203", "6758", "9433"]  # トヨタ、ソニー、KDDI
    
    for ticker_code in tickers:
        print(f"\n【{ticker_code}】")
        ticker = yf.Ticker(f"{ticker_code}.T")
        
        # 配当履歴を取得
        dividends = ticker.dividends
        
        if dividends.empty:
            print(f"❌ 配当データなし")
        else:
            # 2023年の配当のみ表示
            div_2023 = dividends['2023-01-01':'2023-12-31']
            
            if div_2023.empty:
                print(f"⚠️ 2023年の配当データなし")
                print(f"最新の配当:")
                print(dividends.tail(5))
            else:
                print(f"✓ 2023年の配当データ:")
                for date, amount in div_2023.items():
                    record_date = DividendDateCalculator.calculate_record_date(date.to_pydatetime())
                    print(f"  権利落ち日: {date.strftime('%Y-%m-%d')}")
                    print(f"  権利確定日: {record_date.strftime('%Y-%m-%d')}")
                    print(f"  配当金額: {amount:.2f}円")


def check_price_data_around_dividend():
    """配当落ち日周辺の価格データを確認"""
    print("\n\n=== 配当落ち日周辺の価格データ ===\n")
    
    # トヨタの例（2023年3月）
    ticker = yf.Ticker("7203.T")
    
    # 価格データ取得（調整済みと未調整の両方）
    start = "2023-03-25"
    end = "2023-04-05"
    
    print("【トヨタ自動車 - 2023年3月】")
    
    # 未調整価格
    hist = ticker.history(start=start, end=end, auto_adjust=False)
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    
    print("\n日付         | 終値      | 配当    | 前日比")
    print("-" * 50)
    
    prev_close = None
    for date, row in hist.iterrows():
        close = row['Close']
        dividend = row.get('Dividends', 0)
        
        if prev_close:
            change = close - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0
            change_pct = 0
        
        if dividend > 0:
            print(f"{date.strftime('%Y-%m-%d')} | {close:8.2f} | {dividend:6.2f} | {change_pct:+.2f}% ⬅️ 配当落ち")
        else:
            print(f"{date.strftime('%Y-%m-%d')} | {close:8.2f} |        | {change_pct:+.2f}%")
        
        prev_close = close


def check_window_fill_logic():
    """窓埋め判定ロジックの確認"""
    print("\n\n=== 窓埋め判定の検証 ===\n")
    
    # 実際の取引例
    trades = [
        {
            'ticker': '6758',
            'entry_date': '2023-03-29',
            'entry_price': 2310.495,
            'exit_date': '2023-03-30',
            'exit_price': 2335.265,
            'pre_ex_price': 2310,
            'reason': 'Window filled'
        },
        {
            'ticker': '7203',
            'entry_date': '2023-03-29',
            'entry_price': 1861.26,
            'exit_date': '2023-03-31',
            'exit_price': 1870.6,
            'pre_ex_price': 1852,
            'reason': 'Window filled'
        }
    ]
    
    for trade in trades:
        print(f"\n【{trade['ticker']}】")
        print(f"エントリー: {trade['entry_price']:.2f}円")
        print(f"権利落ち前価格: {trade['pre_ex_price']:.2f}円")
        print(f"決済価格: {trade['exit_price']:.2f}円")
        
        # 問題点の分析
        if trade['pre_ex_price'] < trade['entry_price']:
            print(f"⚠️ 権利落ち前価格がエントリー価格より低い！")
            print(f"   これにより、権利落ち日にすぐ窓埋め判定される可能性")
        
        print(f"決済判定: {trade['exit_price']} >= {trade['pre_ex_price']} → {trade['exit_price'] >= trade['pre_ex_price']}")


def analyze_kddi_issue():
    """KDDI（9433）の問題を詳細分析"""
    print("\n\n=== KDDI（9433）の詳細分析 ===\n")
    
    ticker = yf.Ticker("9433.T")
    
    # 全期間の配当データ
    all_dividends = ticker.dividends
    
    if all_dividends.empty:
        print("❌ KDDIの配当データが全く取得できません")
        
        # 会社情報を確認
        info = ticker.info
        print("\n会社情報:")
        print(f"  名称: {info.get('longName', 'N/A')}")
        print(f"  セクター: {info.get('sector', 'N/A')}")
        print(f"  配当利回り: {info.get('dividendYield', 'N/A')}")
        
        # 価格データは取得できるか確認
        hist = ticker.history(period="1mo")
        if not hist.empty:
            print(f"\n✓ 価格データは取得可能（最新: {hist.index[-1].strftime('%Y-%m-%d')}）")
        else:
            print("\n❌ 価格データも取得できません")
    else:
        print(f"✓ 配当データ取得可能: {len(all_dividends)}件")
        print(f"最新の配当: {all_dividends.index[-1].strftime('%Y-%m-%d')} - {all_dividends.iloc[-1]:.2f}円")


def suggest_solutions():
    """解決策の提案"""
    print("\n\n=== 推奨される解決策 ===\n")
    
    print("1. **配当データの代替取得**")
    print("   - yfinanceのアップデート: pip install --upgrade yfinance")
    print("   - 配当カレンダーの手動設定")
    print("   - J-Quants APIの利用検討")
    
    print("\n2. **窓埋め判定の修正**")
    print("   - 権利落ち前日の価格を正確に取得")
    print("   - 配当落ち幅を考慮した判定")
    print("   - 最低保有期間の設定（例：3営業日）")
    
    print("\n3. **バックテストパラメータの調整**")
    print("   - スリッページの現実的な設定（0.3-0.5%）")
    print("   - 手数料の正確な反映")
    print("   - 配当税の適用")
    
    print("\n4. **デバッグモードでの実行**")
    print("   python main.py --log-level DEBUG")


if __name__ == "__main__":
    check_dividend_data()
    check_price_data_around_dividend()
    check_window_fill_logic()
    analyze_kddi_issue()
    suggest_solutions()
