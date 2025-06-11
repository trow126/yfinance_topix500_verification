#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当取り戦略
権利確定日前後の取引戦略を実装
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import log
from ..utils.calendar import DividendDateCalculator, BusinessDayCalculator
from ..utils.config import StrategyConfig


class SignalType(Enum):
    """シグナルタイプ"""
    ENTRY = "ENTRY"
    ADD = "ADD"
    EXIT = "EXIT"
    NONE = "NONE"


class ExitReason(Enum):
    """決済理由"""
    WINDOW_FILLED = "WINDOW_FILLED"  # 窓埋め達成
    MAX_HOLDING_PERIOD = "MAX_HOLDING_PERIOD"  # 最大保有期間
    STOP_LOSS = "STOP_LOSS"  # 損切り
    NONE = "NONE"


@dataclass
class Signal:
    """取引シグナル"""
    ticker: str
    signal_type: SignalType
    date: datetime
    price: float
    shares: int
    reason: str
    metadata: Dict = None


class DividendStrategy:
    """配当取り戦略クラス"""
    
    def __init__(self, config: StrategyConfig):
        """
        初期化
        
        Args:
            config: 戦略設定
        """
        self.config = config
        self.entry_config = config.entry
        self.addition_config = config.addition
        self.exit_config = config.exit
        
        log.info("DividendStrategy initialized")
    
    def check_entry_signal(self,
                         ticker: str,
                         current_date: datetime,
                         dividend_info: Dict,
                         current_price: float) -> Optional[Signal]:
        """
        エントリーシグナルをチェック
        
        Args:
            ticker: 銘柄コード
            current_date: 現在日
            dividend_info: 配当情報
            current_price: 現在価格
            
        Returns:
            エントリーシグナル（なければNone）
        """
        if dividend_info is None:
            return None
        
        record_date = dividend_info['record_date']
        
        # エントリー日を計算
        entry_date = DividendDateCalculator.calculate_entry_date(
            record_date,
            self.entry_config.days_before_record
        )
        
        # 現在日がエントリー日かチェック
        if current_date.date() == entry_date.date():
            # 購入株数を計算
            shares = self._calculate_position_size(
                current_price,
                self.entry_config.position_size
            )
            
            if shares > 0:
                return Signal(
                    ticker=ticker,
                    signal_type=SignalType.ENTRY,
                    date=current_date,
                    price=current_price,
                    shares=shares,
                    reason=f"Entry {self.entry_config.days_before_record} days before record date",
                    metadata={
                        'record_date': record_date,
                        'ex_dividend_date': dividend_info['ex_dividend_date'],
                        'dividend_amount': dividend_info['dividend_amount']
                    }
                )
        
        return None
    
    def check_addition_signal(self,
                            ticker: str,
                            current_date: datetime,
                            position_info: Dict,
                            current_price: float,
                            pre_ex_price: float) -> Optional[Signal]:
        """
        買い増しシグナルをチェック
        
        Args:
            ticker: 銘柄コード
            current_date: 現在日
            position_info: 現在のポジション情報
            current_price: 現在価格
            pre_ex_price: 権利落ち前日の価格
            
        Returns:
            買い増しシグナル（なければNone）
        """
        if not self.addition_config.enabled:
            return None
        
        # 権利落ち日かチェック
        ex_date = position_info.get('ex_dividend_date')
        if ex_date and current_date.date() == ex_date.date():
            # 価格が下落しているかチェック
            if self.addition_config.add_on_drop and current_price < pre_ex_price:
                # 買い増し金額を計算
                add_amount = position_info['initial_value'] * self.addition_config.add_ratio
                shares = self._calculate_position_size(current_price, add_amount)
                
                if shares > 0:
                    drop_pct = (pre_ex_price - current_price) / pre_ex_price * 100
                    return Signal(
                        ticker=ticker,
                        signal_type=SignalType.ADD,
                        date=current_date,
                        price=current_price,
                        shares=shares,
                        reason=f"Add position on ex-dividend drop ({drop_pct:.1f}%)",
                        metadata={
                            'pre_ex_price': pre_ex_price,
                            'drop_percentage': drop_pct
                        }
                    )
        
        return None
    
    def check_exit_signal(self,
                        ticker: str,
                        current_date: datetime,
                        position_info: Dict,
                        current_price: float) -> Optional[Signal]:
        """
        決済シグナルをチェック
        
        Args:
            ticker: 銘柄コード
            current_date: 現在日
            position_info: ポジション情報
            current_price: 現在価格
            
        Returns:
            決済シグナル（なければNone）
        """
        entry_date = position_info['entry_date']
        entry_price = position_info['entry_price']
        avg_price = position_info['average_price']
        total_shares = position_info['total_shares']
        pre_ex_price = position_info.get('pre_ex_price', entry_price)
        
        # 保有日数を計算
        holding_days = BusinessDayCalculator.calculate_business_days(
            entry_date, current_date
        )
        
        # 現在の損益率
        pnl_rate = (current_price - avg_price) / avg_price
        
        # 決済条件をチェック
        exit_reason = ExitReason.NONE
        reason_text = ""
        
        # 1. 窓埋め達成
        if self.exit_config.take_profit_on_window_fill and current_price >= pre_ex_price:
            exit_reason = ExitReason.WINDOW_FILLED
            reason_text = f"Window filled (reached pre-ex price {pre_ex_price:.0f})"
        
        # 2. 最大保有期間
        elif holding_days >= self.exit_config.max_holding_days:
            exit_reason = ExitReason.MAX_HOLDING_PERIOD
            reason_text = f"Max holding period reached ({holding_days} days)"
        
        # 3. 損切り
        elif pnl_rate <= -self.exit_config.stop_loss_pct:
            exit_reason = ExitReason.STOP_LOSS
            reason_text = f"Stop loss triggered ({pnl_rate*100:.1f}%)"
        
        # 決済シグナルを生成
        if exit_reason != ExitReason.NONE:
            return Signal(
                ticker=ticker,
                signal_type=SignalType.EXIT,
                date=current_date,
                price=current_price,
                shares=total_shares,  # 全株売却
                reason=reason_text,
                metadata={
                    'exit_reason': exit_reason.value,
                    'holding_days': holding_days,
                    'pnl_rate': pnl_rate,
                    'entry_price': entry_price,
                    'average_price': avg_price
                }
            )
        
        return None
    
    def _calculate_position_size(self, price: float, investment_amount: float) -> int:
        """
        ポジションサイズ（株数）を計算
        
        Args:
            price: 株価
            investment_amount: 投資金額
            
        Returns:
            購入株数（100株単位）
        """
        if price <= 0:
            return 0
        
        # 最大購入可能株数
        max_shares = int(investment_amount / price)
        
        # 100株単位に調整
        unit_shares = 100
        shares = (max_shares // unit_shares) * unit_shares
        
        return shares
    
    def calculate_pre_ex_price(self,
                             price_history: Dict[str, float],
                             ex_dividend_date: datetime) -> Optional[float]:
        """
        権利落ち前日の価格を取得
        
        Args:
            price_history: 日付と価格の辞書
            ex_dividend_date: 権利落ち日
            
        Returns:
            権利落ち前日の終値
        """
        # 前営業日を計算
        pre_ex_date = BusinessDayCalculator.add_business_days(ex_dividend_date, -1)
        
        # 価格を取得
        return price_history.get(pre_ex_date.strftime('%Y-%m-%d'))
    
    def validate_signal(self, signal: Signal, portfolio_info: Dict) -> bool:
        """
        シグナルの妥当性を検証
        
        Args:
            signal: 取引シグナル
            portfolio_info: ポートフォリオ情報
            
        Returns:
            シグナルが有効な場合True
        """
        # エントリーシグナルの検証
        if signal.signal_type == SignalType.ENTRY:
            # 最大ポジション数チェック
            current_positions = portfolio_info.get('position_count', 0)
            if current_positions >= self.entry_config.max_positions:
                log.warning(f"Max positions reached ({current_positions})")
                return False
            
            # 資金チェック
            required_capital = signal.price * signal.shares
            available_cash = portfolio_info.get('cash', 0)
            if required_capital > available_cash:
                log.warning(f"Insufficient cash: required={required_capital}, available={available_cash}")
                return False
        
        return True


# テスト用コード
if __name__ == "__main__":
    from ..utils.config import StrategyConfig, EntryConfig, AdditionConfig, ExitConfig
    
    # 戦略設定
    entry_config = EntryConfig(
        days_before_record=3,
        position_size=1_000_000,
        max_positions=10
    )
    
    addition_config = AdditionConfig(
        enabled=True,
        add_ratio=0.5,
        add_on_drop=True
    )
    
    exit_config = ExitConfig(
        max_holding_days=20,
        stop_loss_pct=0.1,
        take_profit_on_window_fill=True
    )
    
    strategy_config = StrategyConfig(
        entry=entry_config,
        addition=addition_config,
        exit=exit_config
    )
    
    # 戦略の初期化
    strategy = DividendStrategy(strategy_config)
    
    # テスト用配当情報
    dividend_info = {
        'ex_dividend_date': datetime(2023, 3, 29),
        'record_date': datetime(2023, 3, 31),
        'dividend_amount': 50.0
    }
    
    # エントリーシグナルのテスト
    current_date = datetime(2023, 3, 28)  # エントリー日
    signal = strategy.check_entry_signal(
        ticker="7203",
        current_date=current_date,
        dividend_info=dividend_info,
        current_price=2000.0
    )
    
    if signal:
        print(f"Entry signal: {signal.reason}")
        print(f"Shares: {signal.shares}")
