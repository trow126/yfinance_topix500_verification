#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バックテストエンジン
配当取り戦略のバックテストを実行
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path
import json

from ..utils.logger import log, LogContext
from ..utils.calendar import create_trading_calendar, BusinessDayCalculator
from ..utils.config import Config, ExecutionConfig
from ..data.data_manager import DataManager
from ..strategy.dividend_strategy import DividendStrategy, SignalType
from .portfolio import Portfolio


class BacktestEngine:
    """バックテストエンジンクラス"""
    
    def __init__(self, config: Config):
        """
        初期化
        
        Args:
            config: バックテスト設定
        """
        self.config = config
        
        # コンポーネントの初期化
        self.data_manager = DataManager(config.data_source)
        self.strategy = DividendStrategy(config.strategy)
        self.portfolio = Portfolio(config.backtest.initial_capital)
        self.execution_config = config.execution
        
        # 取引カレンダー
        self.trading_days = create_trading_calendar(
            config.backtest.start_date,
            config.backtest.end_date
        )
        
        # 結果保存用
        self.signals_history = []
        self.daily_stats = []
        
        log.info("BacktestEngine initialized")
        log.info(f"Backtest period: {config.backtest.start_date} to {config.backtest.end_date}")
        log.info(f"Initial capital: {config.backtest.initial_capital:,.0f}")
    
    def run(self) -> Dict:
        """
        バックテストを実行
        
        Returns:
            バックテスト結果
        """
        with LogContext("Backtest execution"):
            # データをロード
            self._load_data()
            
            # 取引日ごとに処理
            for i, current_date in enumerate(self.trading_days):
                if i % 20 == 0:  # 進捗表示
                    progress = (i / len(self.trading_days)) * 100
                    log.info(f"Progress: {progress:.1f}% ({current_date.strftime('%Y-%m-%d')})")
                
                # 日次処理
                self._process_day(current_date.to_pydatetime())
            
            # 最終的な結果を生成
            results = self._generate_results()
            
            log.info("Backtest completed")
            return results
    
    def _load_data(self) -> None:
        """データをロード"""
        log.info(f"Loading data for {len(self.config.universe.tickers)} tickers")
        
        self.data_manager.load_data(
            tickers=self.config.universe.tickers,
            start_date=self.config.backtest.start_date,
            end_date=self.config.backtest.end_date
        )
        
        # データ検証
        validation = self.data_manager.validate_data()
        if validation['errors']:
            log.error(f"Data validation errors: {validation['errors']}")
            raise ValueError("Data validation failed")
        
        if validation['warnings']:
            log.warning(f"Data validation warnings: {validation['warnings']}")
    
    def _process_day(self, current_date: datetime) -> None:
        """
        1日の処理
        
        Args:
            current_date: 処理日
        """
        # 現在の価格を取得
        current_prices = self._get_current_prices(current_date)
        
        # 1. 既存ポジションの処理
        self._process_existing_positions(current_date, current_prices)
        
        # 2. 新規エントリーのチェック
        self._check_new_entries(current_date, current_prices)
        
        # 3. 配当処理
        self._process_dividends(current_date)
        
        # 4. ポートフォリオ評価
        evaluation = self.portfolio.mark_to_market(current_date, current_prices)
        self.daily_stats.append(evaluation)
    
    def _process_existing_positions(self, 
                                  current_date: datetime,
                                  current_prices: Dict[str, float]) -> None:
        """既存ポジションの処理（決済・買い増し）"""
        positions = self.portfolio.position_manager.get_open_positions()
        
        for position in positions:
            ticker = position.ticker
            
            if ticker not in current_prices:
                continue
            
            current_price = current_prices[ticker]
            
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
                # 決済実行
                self._execute_exit(exit_signal, current_price)
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
    
    def _check_new_entries(self,
                         current_date: datetime,
                         current_prices: Dict[str, float]) -> None:
        """新規エントリーのチェック"""
        # ポジション数制限チェック
        if self.portfolio.position_manager.get_position_count() >= self.config.strategy.entry.max_positions:
            return
        
        # 各銘柄をチェック
        for ticker in self.config.universe.tickers:
            # 既にポジションがある場合はスキップ
            if self.portfolio.position_manager.get_position(ticker):
                continue
            
            if ticker not in current_prices:
                continue
            
            current_price = current_prices[ticker]
            
            # 次の配当情報を取得
            dividend_info = self.data_manager.get_next_dividend(ticker, current_date)
            
            if dividend_info:
                # エントリーシグナルをチェック
                entry_signal = self.strategy.check_entry_signal(
                    ticker=ticker,
                    current_date=current_date,
                    dividend_info=dividend_info,
                    current_price=current_price
                )
                
                if entry_signal:
                    # ポートフォリオ情報でバリデーション
                    portfolio_info = {
                        'cash': self.portfolio.cash,
                        'position_count': self.portfolio.position_manager.get_position_count()
                    }
                    
                    if self.strategy.validate_signal(entry_signal, portfolio_info):
                        self._execute_entry(entry_signal, current_price, dividend_info)
    
    def _process_dividends(self, current_date: datetime) -> None:
        """配当処理"""
        positions = self.portfolio.position_manager.get_open_positions()
        
        for position in positions:
            # 権利確定日の翌日に配当を受け取る（簡略化）
            if position.record_date:
                payment_date = BusinessDayCalculator.add_business_days(position.record_date, 1)
                
                if current_date.date() == payment_date.date() and position.dividend_amount:
                    self.portfolio.update_dividend(
                        ticker=position.ticker,
                        dividend_per_share=position.dividend_amount,
                        date=current_date
                    )
    
    def _execute_entry(self,
                      signal,
                      execution_price: float,
                      dividend_info: Optional[Dict] = None) -> None:
        """エントリー（買い）を実行"""
        # 執行価格（スリッページ考慮）
        final_price = execution_price * (1 + self.execution_config.slippage)
        
        # 手数料計算
        trade_amount = final_price * signal.shares
        commission = max(
            trade_amount * self.execution_config.commission,
            self.execution_config.min_commission
        )
        
        # 買い注文実行
        success = self.portfolio.execute_buy(
            ticker=signal.ticker,
            date=signal.date,
            price=final_price,
            shares=signal.shares,
            commission=commission,
            reason=signal.reason,
            dividend_info=dividend_info
        )
        
        # シグナル履歴に記録
        signal_record = {
            'date': signal.date,
            'ticker': signal.ticker,
            'type': signal.signal_type.value,
            'price': final_price,
            'shares': signal.shares,
            'executed': success,
            'reason': signal.reason
        }
        self.signals_history.append(signal_record)
    
    def _execute_exit(self, signal, execution_price: float) -> None:
        """決済（売り）を実行"""
        # 執行価格（スリッページ考慮）
        final_price = execution_price * (1 - self.execution_config.slippage)
        
        # 手数料計算
        trade_amount = final_price * signal.shares
        commission = max(
            trade_amount * self.execution_config.commission,
            self.execution_config.min_commission
        )
        
        # 売り注文実行
        success = self.portfolio.execute_sell(
            ticker=signal.ticker,
            date=signal.date,
            price=final_price,
            commission=commission,
            reason=signal.reason
        )
        
        # シグナル履歴に記録
        signal_record = {
            'date': signal.date,
            'ticker': signal.ticker,
            'type': signal.signal_type.value,
            'price': final_price,
            'shares': signal.shares,
            'executed': success,
            'reason': signal.reason
        }
        self.signals_history.append(signal_record)
    
    def _get_current_prices(self, current_date: datetime) -> Dict[str, float]:
        """現在の価格を取得"""
        prices = {}
        
        for ticker in self.config.universe.tickers:
            price = self.data_manager.get_price_on_date(ticker, current_date)
            if price:
                prices[ticker] = price
        
        return prices
    
    def _generate_results(self) -> Dict:
        """バックテスト結果を生成"""
        # パフォーマンス指標
        metrics = self.portfolio.get_performance_metrics()
        
        # 取引履歴
        trades_df = self.portfolio.position_manager.get_trades_dataframe()
        
        # ポジション履歴
        positions_df = self.portfolio.position_manager.get_positions_summary()
        
        # ポートフォリオ推移
        portfolio_df = self.portfolio.get_portfolio_history_df()
        
        # シグナル履歴
        signals_df = pd.DataFrame(self.signals_history) if self.signals_history else pd.DataFrame()
        
        results = {
            'metrics': metrics,
            'trades': trades_df,
            'positions': positions_df,
            'portfolio_history': portfolio_df,
            'signals': signals_df,
            'config': self._config_to_dict()
        }
        
        # 結果の保存
        self._save_results(results)
        
        return results
    
    def _save_results(self, results: Dict) -> None:
        """結果を保存"""
        output_dir = Path(self.config.output.results_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # メトリクスをJSON形式で保存
        if 'json' in self.config.output.report_format:
            metrics_file = output_dir / f"metrics_{timestamp}.json"
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(results['metrics'], f, indent=2, default=str)
            log.info(f"Metrics saved to {metrics_file}")
        
        # 取引履歴をCSV形式で保存
        if self.config.output.save_trades and 'csv' in self.config.output.report_format:
            if not results['trades'].empty:
                trades_file = output_dir / f"trades_{timestamp}.csv"
                results['trades'].to_csv(trades_file, index=False)
                log.info(f"Trades saved to {trades_file}")
        
        # ポートフォリオ履歴をCSV形式で保存
        if self.config.output.save_portfolio_history and 'csv' in self.config.output.report_format:
            if not results['portfolio_history'].empty:
                portfolio_file = output_dir / f"portfolio_{timestamp}.csv"
                results['portfolio_history'].to_csv(portfolio_file)
                log.info(f"Portfolio history saved to {portfolio_file}")
    
    def _config_to_dict(self) -> Dict:
        """設定を辞書形式に変換"""
        import dataclasses
        return dataclasses.asdict(self.config)


# テスト用コード
if __name__ == "__main__":
    from ..utils.config import load_config
    
    # 設定ファイルを読み込み
    config = load_config("../../config/config.yaml")
    
    # バックテストエンジンを初期化
    engine = BacktestEngine(config)
    
    # バックテスト実行
    results = engine.run()
    
    # 結果表示
    print("\n=== Backtest Results ===")
    for key, value in results['metrics'].items():
        if isinstance(value, float):
            if 'return' in key or 'ratio' in key or 'rate' in key:
                print(f"{key}: {value:.2%}")
            else:
                print(f"{key}: {value:,.2f}")
        else:
            print(f"{key}: {value}")
