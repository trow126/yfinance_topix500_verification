#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
権利落ち日の隠れた買い増しを検出するスクリプト
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


def check_hidden_addition():
    """隠れた買い増しを検出"""
    print("=== 隠れた買い増しの検出 ===\n")
    
    # ポートフォリオ履歴を確認
    portfolio_file = Path("data/results/minimal_debug/portfolio_20250612_162446.csv")
    
    if portfolio_file.exists():
        portfolio_df = pd.read_csv(portfolio_file, index_col=0)
        
        print("【ポジション価値の推移】")
        print("日付         | ポジション価値 | ポジション数")
        print("-" * 50)
        
        for date, row in portfolio_df.iterrows():
            if row['position_count'] > 0:
                print(f"{date} | {row['positions_value']:14,.0f} | {row['position_count']}")
        
        # 3/29と3/30の価値変化を確認
        if '2023-03-29' in portfolio_df.index and '2023-03-30' in portfolio_df.index:
            val_29 = portfolio_df.loc['2023-03-29', 'positions_value']
            val_30 = portfolio_df.loc['2023-03-30', 'positions_value']
            
            print(f"\n3/29のポジション価値: {val_29:,.0f}")
            print(f"3/30のポジション価値: {val_30:,.0f}")
            print(f"変化率: {(val_30/val_29 - 1)*100:.1f}%")
            
            # 株価を逆算
            # 500株での価値と1000株での価値から判断
            implied_shares_29 = 500  # 既知
            implied_price_29 = val_29 / implied_shares_29
            
            # 3/30の価値から株数を推定
            # 株価が大きく変わらないと仮定
            implied_shares_30 = val_30 / implied_price_29
            
            print(f"\n推定株数（3/29）: {implied_shares_29}株")
            print(f"推定株数（3/30）: {implied_shares_30:.0f}株")
            
            if abs(implied_shares_30 - 1000) < 10:
                print("\n⚠️ 3/30に株数が倍増しています！")


def analyze_engine_code():
    """engine.pyの権利落ち日処理を分析"""
    print("\n\n=== engine.pyの権利落ち日処理 ===\n")
    
    print("_process_existing_positions内の権利落ち日処理：")
    print("""
# 買い増しシグナルをチェック（権利落ち日のみ）
if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
    # 権利落ち前日の価格を設定
    pre_ex_date = BusinessDayCalculator.add_business_days(current_date, -1)
    pre_ex_price = self.data_manager.get_price_on_date(ticker, pre_ex_date)
    
    if pre_ex_price:
        self.portfolio.position_manager.update_pre_ex_price(ticker, pre_ex_price)
        
        # 買い増しシグナルをチェック
        add_signal = self.strategy.check_addition_signal(
            ticker=ticker,
            current_date=current_date,
            position_info=position_info,
            current_price=current_price,
            pre_ex_price=pre_ex_price
        )
        
        if add_signal:
            self._execute_entry(add_signal, current_price)
""")
    
    print("\n問題点：")
    print("1. 権利落ち日の処理が無条件で実行されている")
    print("2. addition.enabled のチェックは strategy 側で行われる")
    print("3. しかし、何らかの理由でチェックが効いていない可能性")


def create_fix():
    """修正案の作成"""
    print("\n\n=== 修正案 ===\n")
    
    fix_code = '''
# engine.py の _process_existing_positions を修正

# 買い増しシグナルをチェック（権利落ち日のみ）
if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
    # ↑ ここで addition.enabled をチェック
    
    # 以下既存のコード...
'''
    
    print(fix_code)
    
    print("\nまたは、より根本的な修正：")
    print("""
# 買い増し処理全体をコメントアウト
# if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
#     # 買い増し処理をスキップ
#     pass
""")


def verify_addition_config():
    """買い増し設定の確認"""
    print("\n\n=== 買い増し設定の確認 ===\n")
    
    import yaml
    
    config_file = Path("config/minimal_debug.yaml")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        addition_config = config['strategy']['addition']
        print(f"addition.enabled: {addition_config['enabled']}")
        print(f"addition.add_ratio: {addition_config['add_ratio']}")
        print(f"addition.add_on_drop: {addition_config['add_on_drop']}")
        
        if not addition_config['enabled']:
            print("\n✓ 設定では買い増しは無効になっています")
            print("⚠️ しかし実際には買い増しが実行されています！")


if __name__ == "__main__":
    check_hidden_addition()
    analyze_engine_code()
    create_fix()
    verify_addition_config()
