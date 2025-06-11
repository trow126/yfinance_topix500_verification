#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当取り戦略のテスト
"""

import pytest
from datetime import datetime
from src.strategy.dividend_strategy import DividendStrategy, SignalType, ExitReason
from src.utils.config import StrategyConfig, EntryConfig, AdditionConfig, ExitConfig


@pytest.fixture
def strategy_config():
    """戦略設定のフィクスチャ"""
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
    
    return StrategyConfig(
        entry=entry_config,
        addition=addition_config,
        exit=exit_config
    )


@pytest.fixture
def strategy(strategy_config):
    """戦略インスタンスのフィクスチャ"""
    return DividendStrategy(strategy_config)


class TestDividendStrategy:
    """配当取り戦略のテスト"""
    
    def test_check_entry_signal_valid(self, strategy):
        """有効なエントリーシグナル"""
        # 権利確定日が2023年3月31日の配当情報
        dividend_info = {
            'ex_dividend_date': datetime(2023, 3, 29),
            'record_date': datetime(2023, 3, 31),
            'dividend_amount': 50.0
        }
        
        # 3営業日前の3月28日にエントリー
        current_date = datetime(2023, 3, 28)
        current_price = 2000.0
        
        signal = strategy.check_entry_signal(
            ticker="7203",
            current_date=current_date,
            dividend_info=dividend_info,
            current_price=current_price
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.ENTRY
        assert signal.ticker == "7203"
        assert signal.shares == 500  # 1,000,000 / 2000 = 500株（100株単位）
        assert signal.price == current_price
    
    def test_check_entry_signal_wrong_date(self, strategy):
        """エントリー日以外ではシグナルなし"""
        dividend_info = {
            'ex_dividend_date': datetime(2023, 3, 29),
            'record_date': datetime(2023, 3, 31),
            'dividend_amount': 50.0
        }
        
        # エントリー日の前日
        current_date = datetime(2023, 3, 27)
        current_price = 2000.0
        
        signal = strategy.check_entry_signal(
            ticker="7203",
            current_date=current_date,
            dividend_info=dividend_info,
            current_price=current_price
        )
        
        assert signal is None
    
    def test_check_addition_signal_valid(self, strategy):
        """有効な買い増しシグナル"""
        position_info = {
            'entry_date': datetime(2023, 3, 28),
            'entry_price': 2000.0,
            'average_price': 2000.0,
            'total_shares': 500,
            'initial_value': 1_000_000,
            'ex_dividend_date': datetime(2023, 3, 29)
        }
        
        # 権利落ち日に価格が下落
        current_date = datetime(2023, 3, 29)
        current_price = 1950.0  # 2.5%下落
        pre_ex_price = 2000.0
        
        signal = strategy.check_addition_signal(
            ticker="7203",
            current_date=current_date,
            position_info=position_info,
            current_price=current_price,
            pre_ex_price=pre_ex_price
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.ADD
        assert signal.shares == 200  # 500,000 / 1950 ≈ 256 → 200株（100株単位）
    
    def test_check_addition_signal_no_drop(self, strategy):
        """価格下落なしでは買い増しシグナルなし"""
        position_info = {
            'entry_date': datetime(2023, 3, 28),
            'entry_price': 2000.0,
            'average_price': 2000.0,
            'total_shares': 500,
            'initial_value': 1_000_000,
            'ex_dividend_date': datetime(2023, 3, 29)
        }
        
        # 権利落ち日だが価格上昇
        current_date = datetime(2023, 3, 29)
        current_price = 2050.0  # 上昇
        pre_ex_price = 2000.0
        
        signal = strategy.check_addition_signal(
            ticker="7203",
            current_date=current_date,
            position_info=position_info,
            current_price=current_price,
            pre_ex_price=pre_ex_price
        )
        
        assert signal is None
    
    def test_check_exit_signal_window_filled(self, strategy):
        """窓埋め達成による決済シグナル"""
        position_info = {
            'entry_date': datetime(2023, 3, 28),
            'entry_price': 2000.0,
            'average_price': 1975.0,
            'total_shares': 700,
            'pre_ex_price': 2000.0
        }
        
        # 権利落ち前の価格まで回復
        current_date = datetime(2023, 4, 5)
        current_price = 2001.0
        
        signal = strategy.check_exit_signal(
            ticker="7203",
            current_date=current_date,
            position_info=position_info,
            current_price=current_price
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.EXIT
        assert signal.metadata['exit_reason'] == ExitReason.WINDOW_FILLED.value
        assert signal.shares == 700
    
    def test_check_exit_signal_max_holding(self, strategy):
        """最大保有期間による決済シグナル"""
        position_info = {
            'entry_date': datetime(2023, 3, 1),  # 20営業日以上前
            'entry_price': 2000.0,
            'average_price': 2000.0,
            'total_shares': 500,
            'pre_ex_price': 2000.0
        }
        
        # 20営業日以上経過
        current_date = datetime(2023, 3, 31)
        current_price = 1980.0
        
        signal = strategy.check_exit_signal(
            ticker="7203",
            current_date=current_date,
            position_info=position_info,
            current_price=current_price
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.EXIT
        assert signal.metadata['exit_reason'] == ExitReason.MAX_HOLDING_PERIOD.value
    
    def test_check_exit_signal_stop_loss(self, strategy):
        """損切りによる決済シグナル"""
        position_info = {
            'entry_date': datetime(2023, 3, 28),
            'entry_price': 2000.0,
            'average_price': 2000.0,
            'total_shares': 500,
            'pre_ex_price': 2000.0
        }
        
        # 10%以上下落
        current_date = datetime(2023, 3, 30)
        current_price = 1790.0  # 10.5%下落
        
        signal = strategy.check_exit_signal(
            ticker="7203",
            current_date=current_date,
            position_info=position_info,
            current_price=current_price
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.EXIT
        assert signal.metadata['exit_reason'] == ExitReason.STOP_LOSS.value
    
    def test_calculate_position_size(self, strategy):
        """ポジションサイズ計算のテスト"""
        # 100株単位での計算
        shares = strategy._calculate_position_size(2000.0, 1_000_000)
        assert shares == 500
        
        # 端数切り捨て
        shares = strategy._calculate_position_size(2150.0, 1_000_000)
        assert shares == 400  # 465株 → 400株
        
        # 価格が0以下
        shares = strategy._calculate_position_size(0.0, 1_000_000)
        assert shares == 0
    
    def test_validate_signal_max_positions(self, strategy):
        """最大ポジション数の検証"""
        from src.strategy.dividend_strategy import Signal
        
        signal = Signal(
            ticker="7203",
            signal_type=SignalType.ENTRY,
            date=datetime.now(),
            price=2000.0,
            shares=500,
            reason="Test"
        )
        
        # すでに最大ポジション数に達している
        portfolio_info = {
            'position_count': 10,  # 最大値
            'cash': 5_000_000
        }
        
        assert strategy.validate_signal(signal, portfolio_info) == False
    
    def test_validate_signal_insufficient_cash(self, strategy):
        """資金不足の検証"""
        from src.strategy.dividend_strategy import Signal
        
        signal = Signal(
            ticker="7203",
            signal_type=SignalType.ENTRY,
            date=datetime.now(),
            price=2000.0,
            shares=500,
            reason="Test"
        )
        
        # 資金不足
        portfolio_info = {
            'position_count': 5,
            'cash': 500_000  # 必要額は1,000,000
        }
        
        assert strategy.validate_signal(signal, portfolio_info) == False
