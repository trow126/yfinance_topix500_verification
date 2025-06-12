#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポートフォリオ管理
資金管理と全体パフォーマンスの追跡
"""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from ..utils.logger import log
from ..strategy.position_manager import PositionManager, Trade, TradeType


class Portfolio:
    """ポートフォリオ管理クラス"""
    
    def __init__(self, initial_capital: float):
        """
        初期化
        
        Args:
            initial_capital: 初期資本
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position_manager = PositionManager()
        
        # パフォーマンス履歴
        self.portfolio_history = []
        self.daily_returns = []
        
        # 累積統計
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0
        self.total_dividend = 0.0
        
        log.info(f"Portfolio initialized with capital: {initial_capital:,.0f}")
    
    def execute_buy(self,
                   ticker: str,
                   date: datetime,
                   price: float,
                   shares: int,
                   commission: float,
                   reason: str,
                   dividend_info: Optional[Dict] = None) -> bool:
        """
        買い注文を実行
        
        Args:
            ticker: 銘柄コード
            date: 取引日
            price: 取引価格
            shares: 株数
            commission: 手数料
            reason: 取引理由
            dividend_info: 配当情報
            
        Returns:
            実行成功の場合True
        """
        # 必要資金を計算
        required_cash = price * shares + commission
        
        # 資金チェック
        if required_cash > self.cash:
            log.warning(f"Insufficient cash for {ticker}: required={required_cash:.0f}, available={self.cash:.0f}")
            return False
        
        # ポジションの有無をチェック
        if self.position_manager.get_position(ticker):
            # 買い増し理由を明示的にチェック
            if reason and ("Add" in reason or "add" in reason):
                # 買い増しの場合のみ追加
                self.position_manager.add_to_position(
                    ticker=ticker,
                    date=date,
                    price=price,
                    shares=shares,
                    commission=commission,
                    reason=reason
                )
            else:
                # 既存ポジションがある場合はスキップ
                log.warning(f"Position already exists for {ticker}, skipping duplicate buy. Reason: {reason}")
                return False
        else:
            # 新規ポジション
            self.position_manager.open_position(
                ticker=ticker,
                date=date,
                price=price,
                shares=shares,
                commission=commission,
                reason=reason,
                dividend_info=dividend_info
            )
        
        # 資金を更新
        self.cash -= required_cash
        self.total_commission += commission
        self.total_trades += 1
        
        log.info(f"Buy executed: {ticker} {shares}@{price:.0f}, cash remaining: {self.cash:,.0f}")
        
        return True
    
    def execute_sell(self,
                    ticker: str,
                    date: datetime,
                    price: float,
                    commission: float,
                    reason: str) -> bool:
        """
        売り注文を実行
        
        Args:
            ticker: 銘柄コード
            date: 取引日
            price: 取引価格
            commission: 手数料
            reason: 取引理由
            
        Returns:
            実行成功の場合True
        """
        # ポジションチェック
        position = self.position_manager.get_position(ticker)
        if not position:
            log.warning(f"No position to sell for {ticker}")
            return False
        
        shares = position.total_shares
        
        # ポジションをクローズ
        closed_position = self.position_manager.close_position(
            ticker=ticker,
            date=date,
            price=price,
            commission=commission,
            reason=reason
        )
        
        # 資金を更新
        proceeds = price * shares - commission
        self.cash += proceeds
        self.total_commission += commission
        self.total_trades += 1
        
        # 勝敗をカウント
        if closed_position.realized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        log.info(f"Sell executed: {ticker} {shares}@{price:.0f}, PnL: {closed_position.realized_pnl:,.0f}")
        
        return True
    
    def update_dividend(self, ticker: str, dividend_per_share: float, date: datetime) -> None:
        """
        配当金を受け取り
        
        Args:
            ticker: 銘柄コード
            dividend_per_share: 1株あたり配当
            date: 受取日
        """
        position = self.position_manager.get_position(ticker)
        if position:
            dividend_amount = dividend_per_share * position.total_shares
            self.cash += dividend_amount
            self.total_dividend += dividend_amount
            
            # ポジションに記録
            self.position_manager.update_dividend_received(ticker, dividend_per_share)
            
            log.info(f"Dividend received: {ticker} {dividend_amount:,.0f}")
    
    def mark_to_market(self, date: datetime, prices: Dict[str, float]) -> Dict:
        """
        時価評価を実行
        
        Args:
            date: 評価日
            prices: 現在価格の辞書
            
        Returns:
            ポートフォリオ評価結果
        """
        # ポジションの時価総額
        positions_value = self.position_manager.get_total_market_value(prices)
        
        # ポートフォリオ総額
        total_value = self.cash + positions_value
        
        # 前日からのリターン
        if self.portfolio_history:
            prev_value = self.portfolio_history[-1]['total_value']
            daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0
        else:
            daily_return = 0
        
        # 累積リターン
        total_return = (total_value - self.initial_capital) / self.initial_capital
        
        # 評価結果
        evaluation = {
            'date': date,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_value': total_value,
            'daily_return': daily_return,
            'total_return': total_return,
            'position_count': self.position_manager.get_position_count()
        }
        
        # 履歴に追加
        self.portfolio_history.append(evaluation)
        if daily_return != 0:
            self.daily_returns.append(daily_return)
        
        return evaluation
    
    def get_performance_metrics(self) -> Dict:
        """
        パフォーマンス指標を計算
        
        Returns:
            各種パフォーマンス指標
        """
        if not self.portfolio_history:
            return {}
        
        # 基本統計
        final_value = self.portfolio_history[-1]['total_value']
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # 勝率
        total_closed = self.winning_trades + self.losing_trades
        win_rate = self.winning_trades / total_closed if total_closed > 0 else 0
        
        # 日次リターンの統計
        if self.daily_returns:
            daily_returns_array = np.array(self.daily_returns)
            
            # 年率リターン（252営業日）
            avg_daily_return = np.mean(daily_returns_array)
            annualized_return = (1 + avg_daily_return) ** 252 - 1
            
            # ボラティリティ
            daily_volatility = np.std(daily_returns_array)
            annualized_volatility = daily_volatility * np.sqrt(252)
            
            # シャープレシオ（リスクフリーレート0.01と仮定）
            risk_free_rate = 0.01
            excess_return = annualized_return - risk_free_rate
            sharpe_ratio = excess_return / annualized_volatility if annualized_volatility > 0 else 0
            
            # 最大ドローダウン
            portfolio_values = pd.Series([h['total_value'] for h in self.portfolio_history])
            running_max = portfolio_values.expanding().max()
            drawdown = (portfolio_values - running_max) / running_max
            max_drawdown = drawdown.min()
        else:
            annualized_return = 0
            annualized_volatility = 0
            sharpe_ratio = 0
            max_drawdown = 0
        
        # プロフィットファクター
        closed_positions = self.position_manager.closed_positions
        if closed_positions:
            profits = sum(p.realized_pnl for p in closed_positions if p.realized_pnl > 0)
            losses = abs(sum(p.realized_pnl for p in closed_positions if p.realized_pnl < 0))
            profit_factor = profits / losses if losses > 0 else float('inf')
        else:
            profit_factor = 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_commission': self.total_commission,
            'total_dividend': self.total_dividend,
            'final_value': final_value
        }
    
    def get_portfolio_history_df(self) -> pd.DataFrame:
        """ポートフォリオ履歴をDataFrame形式で取得"""
        if not self.portfolio_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.portfolio_history)
        df.set_index('date', inplace=True)
        return df
    
    def get_current_holdings(self) -> pd.DataFrame:
        """現在の保有銘柄一覧を取得"""
        positions = self.position_manager.get_open_positions()
        
        if not positions:
            return pd.DataFrame()
        
        holdings = []
        for pos in positions:
            holdings.append({
                'ticker': pos.ticker,
                'shares': pos.total_shares,
                'average_price': pos.average_price,
                'cost_basis': pos.average_price * pos.total_shares,
                'entry_date': pos.entry_date
            })
        
        return pd.DataFrame(holdings)


# テスト用コード
if __name__ == "__main__":
    # ポートフォリオのテスト
    portfolio = Portfolio(initial_capital=10_000_000)
    
    # 買い注文
    success = portfolio.execute_buy(
        ticker="7203",
        date=datetime(2023, 3, 28),
        price=2000.0,
        shares=500,
        commission=500.0,
        reason="Entry signal"
    )
    print(f"Buy executed: {success}")
    print(f"Cash remaining: {portfolio.cash:,.0f}")
    
    # 時価評価
    prices = {"7203": 2050.0}
    evaluation = portfolio.mark_to_market(datetime(2023, 3, 29), prices)
    print(f"\nPortfolio value: {evaluation['total_value']:,.0f}")
    print(f"Positions value: {evaluation['positions_value']:,.0f}")
    
    # 売り注文
    success = portfolio.execute_sell(
        ticker="7203",
        date=datetime(2023, 4, 1),
        price=2100.0,
        commission=500.0,
        reason="Exit signal"
    )
    print(f"\nSell executed: {success}")
    print(f"Cash after sell: {portfolio.cash:,.0f}")
    
    # パフォーマンス指標
    metrics = portfolio.get_performance_metrics()
    print(f"\nTotal return: {metrics['total_return']:.2%}")
    print(f"Win rate: {metrics['win_rate']:.2%}")
