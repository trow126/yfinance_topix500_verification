#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最低保有期間を考慮した修正版実行スクリプト
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config, Config
from src.backtest.engine import BacktestEngine
from src.utils.logger import log
import json


class ModifiedBacktestEngine(BacktestEngine):
    """修正版バックテストエンジン（最低保有期間を考慮）"""
    
    MIN_HOLDING_DAYS = 3  # 最低保有期間
    
    def _process_existing_positions(self, current_date, current_prices):
        """既存ポジションの処理（修正版）"""
        positions = self.portfolio.position_manager.get_open_positions()
        
        for position in positions:
            ticker = position.ticker
            
            if ticker not in current_prices:
                continue
            
            current_price = current_prices[ticker]
            
            # 保有日数を計算
            from src.utils.calendar import BusinessDayCalculator
            holding_days = BusinessDayCalculator.calculate_business_days(
                position.entry_date, current_date
            )
            
            # 最低保有期間チェック
            if holding_days < self.MIN_HOLDING_DAYS:
                log.debug(f"{ticker}: 最低保有期間未満 ({holding_days}日 < {self.MIN_HOLDING_DAYS}日)")
                continue
            
            # ポジション情報を辞書形式に変換
            position_info = {
                'entry_date': position.entry_date,
                'entry_price': position.entry_price,
                'average_price': position.average_price,
                'total_shares': position.total_shares,
                'initial_value': position.entry_price * position.total_shares,
                'ex_dividend_date': position.ex_dividend_date,
                'pre_ex_price': position.pre_ex_price or position.entry_price
            }
            
            # 決済シグナルをチェック
            exit_signal = self.strategy.check_exit_signal(
                ticker=ticker,
                current_date=current_date,
                position_info=position_info,
                current_price=current_price
            )
            
            if exit_signal:
                # 再度最低保有期間チェック（念のため）
                if holding_days >= self.MIN_HOLDING_DAYS:
                    self._execute_exit(exit_signal, current_price)
                    log.info(f"{ticker}: 決済実行（保有{holding_days}日）")
                continue
            
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


def run_modified_backtest():
    """修正版バックテストを実行"""
    print("=" * 70)
    print("配当取り戦略バックテスト - 修正版")
    print("最低保有期間3日を設定")
    print("=" * 70)
    
    # 設定読み込み
    config = load_config("config/fixed_config.yaml")
    
    print(f"\n実行条件:")
    print(f"  期間: {config.backtest.start_date} ～ {config.backtest.end_date}")
    print(f"  銘柄: {', '.join(config.universe.tickers)}")
    print(f"  初期資本: {config.backtest.initial_capital:,}円")
    print(f"  最低保有期間: {ModifiedBacktestEngine.MIN_HOLDING_DAYS}日")
    
    # バックテスト実行
    print("\nバックテストを開始します...")
    start_time = datetime.now()
    
    try:
        # 修正版エンジンを使用
        engine = ModifiedBacktestEngine(config)
        results = engine.run()
        
        # 実行時間
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 結果表示
        print("\n" + "=" * 70)
        print("バックテスト結果")
        print("=" * 70)
        
        metrics = results["metrics"]
        
        print(f"\n【リターン指標】")
        print(f"  総リターン: {metrics.get('total_return', 0):.2%}")
        print(f"  年率リターン: {metrics.get('annualized_return', 0):.2%}")
        
        print(f"\n【リスク指標】")
        print(f"  最大ドローダウン: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  シャープレシオ: {metrics.get('sharpe_ratio', 0):.2f}")
        
        print(f"\n【取引統計】")
        print(f"  総取引数: {metrics.get('total_trades', 0)}")
        print(f"  勝率: {metrics.get('win_rate', 0):.1%}")
        
        # ポジション詳細の確認
        if 'positions' in results and not results['positions'].empty:
            positions_df = results['positions']
            
            # 保有期間を計算
            positions_df['entry_date'] = pd.to_datetime(positions_df['entry_date'])
            positions_df['exit_date'] = pd.to_datetime(positions_df['exit_date'])
            positions_df['holding_days'] = (positions_df['exit_date'] - positions_df['entry_date']).dt.days
            
            print(f"\n【保有期間統計】")
            print(f"  平均保有期間: {positions_df['holding_days'].mean():.1f}日")
            print(f"  最短保有期間: {positions_df['holding_days'].min()}日")
            print(f"  最長保有期間: {positions_df['holding_days'].max()}日")
        
        print(f"\n【実行情報】")
        print(f"  実行時間: {execution_time:.1f}秒")
        
        # 妥当性チェック
        print("\n【妥当性チェック】")
        if metrics.get("annualized_return", 0) > 0.15:
            print("  ⚠️ 年率リターンがまだ高すぎます")
        else:
            print("  ✅ 年率リターンは現実的な範囲です")
        
        if metrics.get("win_rate", 0) > 0.65:
            print("  ⚠️ 勝率がまだ高すぎます")
        else:
            print("  ✅ 勝率は現実的な範囲です")
        
        if abs(metrics.get("max_drawdown", 0)) < 0.05:
            print("  ⚠️ 最大ドローダウンが小さすぎます")
        else:
            print("  ✅ 最大ドローダウンは現実的な範囲です")
        
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import pandas as pd
    run_modified_backtest()
