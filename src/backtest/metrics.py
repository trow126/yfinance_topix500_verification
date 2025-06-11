#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
評価指標計算
バックテスト結果の詳細な分析と評価指標の計算
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from ..utils.logger import log


class MetricsCalculator:
    """評価指標計算クラス"""
    
    @staticmethod
    def calculate_returns_metrics(portfolio_history: pd.DataFrame) -> Dict:
        """
        リターン関連の指標を計算
        
        Args:
            portfolio_history: ポートフォリオ履歴
            
        Returns:
            リターン指標
        """
        if portfolio_history.empty:
            return {}
        
        # 総リターン
        initial_value = portfolio_history['total_value'].iloc[0]
        final_value = portfolio_history['total_value'].iloc[-1]
        total_return = (final_value - initial_value) / initial_value
        
        # 年率リターン
        days = len(portfolio_history)
        years = days / 252  # 営業日ベース
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 月次リターン
        monthly_returns = portfolio_history['total_value'].resample('M').last().pct_change()
        avg_monthly_return = monthly_returns.mean()
        
        # 最良・最悪月
        best_month = monthly_returns.max()
        worst_month = monthly_returns.min()
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'avg_monthly_return': avg_monthly_return,
            'best_month_return': best_month,
            'worst_month_return': worst_month
        }
    
    @staticmethod
    def calculate_risk_metrics(portfolio_history: pd.DataFrame) -> Dict:
        """
        リスク関連の指標を計算
        
        Args:
            portfolio_history: ポートフォリオ履歴
            
        Returns:
            リスク指標
        """
        if portfolio_history.empty or len(portfolio_history) < 2:
            return {}
        
        # 日次リターン
        daily_returns = portfolio_history['total_value'].pct_change().dropna()
        
        # ボラティリティ
        daily_vol = daily_returns.std()
        annualized_vol = daily_vol * np.sqrt(252)
        
        # 下方偏差（ソルティノレシオ用）
        negative_returns = daily_returns[daily_returns < 0]
        downside_deviation = np.sqrt(np.mean(negative_returns ** 2)) * np.sqrt(252)
        
        # 最大ドローダウン
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # ドローダウン期間
        drawdown_start = drawdown.idxmin()
        recovery_date = None
        if drawdown_start in cumulative.index:
            peak_value = running_max.loc[drawdown_start]
            recovery_mask = cumulative.loc[drawdown_start:] >= peak_value
            if recovery_mask.any():
                recovery_date = cumulative.loc[drawdown_start:][recovery_mask].index[0]
        
        drawdown_days = (recovery_date - drawdown_start).days if recovery_date else None
        
        # VaR（95%信頼区間）
        var_95 = daily_returns.quantile(0.05) * np.sqrt(252)
        
        # CVaR（期待ショートフォール）
        cvar_95 = daily_returns[daily_returns <= daily_returns.quantile(0.05)].mean() * np.sqrt(252)
        
        return {
            'annualized_volatility': annualized_vol,
            'downside_deviation': downside_deviation,
            'max_drawdown': max_drawdown,
            'max_drawdown_days': drawdown_days,
            'var_95': var_95,
            'cvar_95': cvar_95
        }
    
    @staticmethod
    def calculate_ratio_metrics(returns_metrics: Dict, risk_metrics: Dict) -> Dict:
        """
        各種レシオを計算
        
        Args:
            returns_metrics: リターン指標
            risk_metrics: リスク指標
            
        Returns:
            レシオ指標
        """
        ratios = {}
        
        # シャープレシオ
        risk_free_rate = 0.01  # 1%のリスクフリーレート
        excess_return = returns_metrics.get('annualized_return', 0) - risk_free_rate
        volatility = risk_metrics.get('annualized_volatility', 1)
        ratios['sharpe_ratio'] = excess_return / volatility if volatility > 0 else 0
        
        # ソルティノレシオ
        downside_dev = risk_metrics.get('downside_deviation', 1)
        ratios['sortino_ratio'] = excess_return / downside_dev if downside_dev > 0 else 0
        
        # カルマーレシオ
        max_dd = abs(risk_metrics.get('max_drawdown', 1))
        ratios['calmar_ratio'] = returns_metrics.get('annualized_return', 0) / max_dd if max_dd > 0 else 0
        
        return ratios
    
    @staticmethod
    def calculate_trade_metrics(trades_df: pd.DataFrame, positions_df: pd.DataFrame) -> Dict:
        """
        取引関連の指標を計算
        
        Args:
            trades_df: 取引履歴
            positions_df: ポジション履歴
            
        Returns:
            取引指標
        """
        metrics = {}
        
        if not trades_df.empty:
            # 取引回数
            metrics['total_trades'] = len(trades_df)
            metrics['buy_trades'] = len(trades_df[trades_df['type'] == 'BUY'])
            metrics['sell_trades'] = len(trades_df[trades_df['type'] == 'SELL'])
            
            # 平均取引金額
            metrics['avg_trade_amount'] = trades_df['amount'].mean()
            
            # 総手数料
            metrics['total_commission'] = trades_df['commission'].sum()
        
        if not positions_df.empty:
            closed_positions = positions_df[positions_df['status'] == 'CLOSED']
            
            if not closed_positions.empty:
                # 勝率
                winning_positions = closed_positions[closed_positions['realized_pnl'] > 0]
                metrics['win_rate'] = len(winning_positions) / len(closed_positions)
                
                # 平均利益・損失
                profits = closed_positions[closed_positions['realized_pnl'] > 0]['realized_pnl']
                losses = closed_positions[closed_positions['realized_pnl'] < 0]['realized_pnl']
                
                metrics['avg_profit'] = profits.mean() if len(profits) > 0 else 0
                metrics['avg_loss'] = losses.mean() if len(losses) > 0 else 0
                
                # プロフィットファクター
                total_profits = profits.sum() if len(profits) > 0 else 0
                total_losses = abs(losses.sum()) if len(losses) > 0 else 1
                metrics['profit_factor'] = total_profits / total_losses
                
                # 平均保有期間
                if 'exit_date' in closed_positions.columns and 'entry_date' in closed_positions.columns:
                    closed_positions['holding_days'] = pd.to_datetime(closed_positions['exit_date']) - pd.to_datetime(closed_positions['entry_date'])
                    metrics['avg_holding_days'] = closed_positions['holding_days'].dt.days.mean()
        
        return metrics
    
    @staticmethod
    def calculate_dividend_metrics(positions_df: pd.DataFrame) -> Dict:
        """
        配当関連の指標を計算
        
        Args:
            positions_df: ポジション履歴
            
        Returns:
            配当指標
        """
        if positions_df.empty or 'dividend_received' not in positions_df.columns:
            return {}
        
        total_dividend = positions_df['dividend_received'].sum()
        positions_with_dividend = positions_df[positions_df['dividend_received'] > 0]
        
        return {
            'total_dividend_received': total_dividend,
            'positions_with_dividend': len(positions_with_dividend),
            'avg_dividend_per_position': positions_with_dividend['dividend_received'].mean() if len(positions_with_dividend) > 0 else 0
        }
    
    @staticmethod
    def generate_summary_report(results: Dict) -> str:
        """
        サマリーレポートを生成
        
        Args:
            results: バックテスト結果
            
        Returns:
            レポート文字列
        """
        metrics = results.get('metrics', {})
        
        report = []
        report.append("=" * 60)
        report.append("BACKTEST SUMMARY REPORT")
        report.append("=" * 60)
        
        # リターン
        report.append("\n[Returns]")
        report.append(f"Total Return: {metrics.get('total_return', 0):.2%}")
        report.append(f"Annualized Return: {metrics.get('annualized_return', 0):.2%}")
        
        # リスク
        report.append("\n[Risk]")
        report.append(f"Annual Volatility: {metrics.get('annualized_volatility', 0):.2%}")
        report.append(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
        
        # レシオ
        report.append("\n[Risk-Adjusted Returns]")
        report.append(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        report.append(f"Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}")
        
        # 取引統計
        report.append("\n[Trading Statistics]")
        report.append(f"Total Trades: {metrics.get('total_trades', 0)}")
        report.append(f"Win Rate: {metrics.get('win_rate', 0):.2%}")
        report.append(f"Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        
        # 配当
        report.append("\n[Dividends]")
        report.append(f"Total Dividend: ¥{metrics.get('total_dividend', 0):,.0f}")
        
        # 最終結果
        report.append("\n[Final Results]")
        report.append(f"Final Portfolio Value: ¥{metrics.get('final_value', 0):,.0f}")
        report.append(f"Total Commission Paid: ¥{metrics.get('total_commission', 0):,.0f}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


class BacktestVisualizer:
    """バックテスト結果の可視化クラス"""
    
    @staticmethod
    def plot_portfolio_performance(portfolio_history: pd.DataFrame, save_path: Optional[Path] = None) -> None:
        """
        ポートフォリオパフォーマンスをプロット
        
        Args:
            portfolio_history: ポートフォリオ履歴
            save_path: 保存パス
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. ポートフォリオ価値の推移
        ax = axes[0, 0]
        ax.plot(portfolio_history.index, portfolio_history['total_value'] / 1e6, 'b-', linewidth=2)
        ax.set_title('Portfolio Value Over Time')
        ax.set_xlabel('Date')
        ax.set_ylabel('Portfolio Value (Million Yen)')
        ax.grid(True, alpha=0.3)
        
        # 2. 累積リターン
        ax = axes[0, 1]
        cumulative_returns = (portfolio_history['total_value'] / portfolio_history['total_value'].iloc[0] - 1) * 100
        ax.plot(portfolio_history.index, cumulative_returns, 'g-', linewidth=2)
        ax.set_title('Cumulative Returns')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return (%)')
        ax.grid(True, alpha=0.3)
        
        # 3. ドローダウン
        ax = axes[1, 0]
        running_max = portfolio_history['total_value'].expanding().max()
        drawdown = (portfolio_history['total_value'] - running_max) / running_max * 100
        ax.fill_between(portfolio_history.index, drawdown, 0, color='red', alpha=0.3)
        ax.plot(portfolio_history.index, drawdown, 'r-', linewidth=1)
        ax.set_title('Drawdown')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.grid(True, alpha=0.3)
        
        # 4. 月次リターン分布
        ax = axes[1, 1]
        monthly_returns = portfolio_history['total_value'].resample('M').last().pct_change() * 100
        ax.hist(monthly_returns.dropna(), bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        ax.set_title('Monthly Returns Distribution')
        ax.set_xlabel('Monthly Return (%)')
        ax.set_ylabel('Frequency')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()


# テスト用コード
if __name__ == "__main__":
    # サンプルデータの作成
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    portfolio_values = 10_000_000 * (1 + np.random.randn(len(dates)).cumsum() * 0.001)
    
    portfolio_history = pd.DataFrame({
        'total_value': portfolio_values,
        'cash': portfolio_values * 0.3,
        'positions_value': portfolio_values * 0.7
    }, index=dates)
    
    # メトリクス計算
    returns_metrics = MetricsCalculator.calculate_returns_metrics(portfolio_history)
    risk_metrics = MetricsCalculator.calculate_risk_metrics(portfolio_history)
    ratio_metrics = MetricsCalculator.calculate_ratio_metrics(returns_metrics, risk_metrics)
    
    print("Returns Metrics:")
    for k, v in returns_metrics.items():
        print(f"  {k}: {v:.4f}")
    
    print("\nRisk Metrics:")
    for k, v in risk_metrics.items():
        print(f"  {k}: {v:.4f}")
    
    print("\nRatio Metrics:")
    for k, v in ratio_metrics.items():
        print(f"  {k}: {v:.4f}")
