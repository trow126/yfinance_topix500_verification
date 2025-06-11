#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポジション管理のテスト
"""

import pytest
from datetime import datetime
from src.strategy.position_manager import PositionManager, Position, Trade, TradeType, PositionStatus


class TestPositionManager:
    """ポジション管理のテスト"""
    
    @pytest.fixture
    def position_manager(self):
        """ポジションマネージャーのフィクスチャ"""
        return PositionManager()
    
    def test_open_position(self, position_manager):
        """新規ポジションの開設"""
        dividend_info = {
            'ex_dividend_date': datetime(2023, 3, 29),
            'record_date': datetime(2023, 3, 31),
            'dividend_amount': 50.0
        }
        
        position = position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal",
            dividend_info=dividend_info
        )
        
        assert position.ticker == "7203"
        assert position.status == PositionStatus.OPEN
        assert position.total_shares == 500
        assert position.average_price == 2000.0
        assert position.ex_dividend_date == datetime(2023, 3, 29)
        assert position.record_date == datetime(2023, 3, 31)
        assert position.dividend_amount == 50.0
        assert len(position.trades) == 1
        assert position_manager.get_position_count() == 1
    
    def test_open_position_duplicate(self, position_manager):
        """重複ポジションの開設エラー"""
        position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        with pytest.raises(ValueError):
            position_manager.open_position(
                ticker="7203",
                date=datetime(2023, 3, 29),
                price=1950.0,
                shares=300,
                commission=300.0,
                reason="Duplicate"
            )
    
    def test_add_to_position(self, position_manager):
        """ポジションへの追加"""
        # 初期ポジション
        position = position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        # ポジション追加
        updated_position = position_manager.add_to_position(
            ticker="7203",
            date=datetime(2023, 3, 29),
            price=1950.0,
            shares=300,
            commission=300.0,
            reason="Add on drop"
        )
        
        # 平均価格の検証
        # (2000 * 500 + 1950 * 300) / 800 = 1981.25
        expected_avg_price = (2000 * 500 + (1950 * 300 + 300)) / 800
        
        assert updated_position.total_shares == 800
        assert abs(updated_position.average_price - expected_avg_price) < 1
        assert len(updated_position.trades) == 2
        assert updated_position.total_commission == 800.0
    
    def test_close_position(self, position_manager):
        """ポジションのクローズ"""
        # ポジション開設
        position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        # ポジションクローズ
        closed_position = position_manager.close_position(
            ticker="7203",
            date=datetime(2023, 4, 5),
            price=2100.0,
            commission=500.0,
            reason="Window filled"
        )
        
        assert closed_position.status == PositionStatus.CLOSED
        assert closed_position.exit_date == datetime(2023, 4, 5)
        assert closed_position.exit_price == 2100.0
        assert closed_position.exit_reason == "Window filled"
        
        # 実現損益の計算
        # 売却収入: 2100 * 500 - 500 = 1,049,500
        # 取得原価: 2000 * 500 + 500 = 1,000,500
        # 実現損益: 1,049,500 - 1,000,500 = 49,000
        assert closed_position.realized_pnl == 49_000
        
        # ポジションが削除されていることを確認
        assert position_manager.get_position("7203") is None
        assert position_manager.get_position_count() == 0
        assert len(position_manager.closed_positions) == 1
    
    def test_update_dividend_received(self, position_manager):
        """配当受取の更新"""
        position = position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        position_manager.update_dividend_received("7203", 50.0)
        
        assert position.dividend_received == 25_000  # 50 * 500
    
    def test_update_pre_ex_price(self, position_manager):
        """権利落ち前日価格の更新"""
        position = position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        position_manager.update_pre_ex_price("7203", 2050.0)
        
        assert position.pre_ex_price == 2050.0
    
    def test_get_total_market_value(self, position_manager):
        """時価総額の計算"""
        # 複数ポジション
        position_manager.open_position("7203", datetime.now(), 2000.0, 500, 500.0, "Entry")
        position_manager.open_position("6758", datetime.now(), 10000.0, 100, 500.0, "Entry")
        
        prices = {
            "7203": 2100.0,
            "6758": 10500.0
        }
        
        total_value = position_manager.get_total_market_value(prices)
        expected = 2100.0 * 500 + 10500.0 * 100
        
        assert total_value == expected
    
    def test_get_trades_dataframe(self, position_manager):
        """取引履歴のDataFrame取得"""
        # 取引実行
        position_manager.open_position("7203", datetime(2023, 3, 28), 2000.0, 500, 500.0, "Entry")
        position_manager.add_to_position("7203", datetime(2023, 3, 29), 1950.0, 300, 300.0, "Add")
        position_manager.close_position("7203", datetime(2023, 4, 5), 2100.0, 500.0, "Exit")
        
        trades_df = position_manager.get_trades_dataframe()
        
        assert len(trades_df) == 3
        assert trades_df['ticker'].tolist() == ["7203", "7203", "7203"]
        assert trades_df['type'].tolist() == ["BUY", "BUY", "SELL"]
        assert trades_df['shares'].tolist() == [500, 300, 800]
    
    def test_position_holding_days(self, position_manager):
        """保有日数の計算"""
        position = position_manager.open_position(
            ticker="7203",
            date=datetime(2023, 3, 28),
            price=2000.0,
            shares=500,
            commission=500.0,
            reason="Entry signal"
        )
        
        # オープンポジションの保有日数
        holding_days = position.get_holding_days(datetime(2023, 4, 5))
        assert holding_days == 8
        
        # クローズ後の保有日数
        position_manager.close_position("7203", datetime(2023, 4, 10), 2100.0, 500.0, "Exit")
        holding_days = position.get_holding_days(datetime(2023, 4, 20))  # 任意の日付
        assert holding_days == 13  # 3/28から4/10まで


class TestPosition:
    """ポジションクラスのテスト"""
    
    def test_calculate_unrealized_pnl(self):
        """未実現損益の計算"""
        position = Position(
            ticker="7203",
            status=PositionStatus.OPEN,
            entry_date=datetime(2023, 3, 28),
            entry_price=2000.0,
            total_shares=500,
            average_price=2000.0
        )
        
        # 価格上昇時
        unrealized_pnl = position.calculate_unrealized_pnl(2100.0)
        assert unrealized_pnl == 50_000  # (2100 - 2000) * 500
        
        # 価格下落時
        unrealized_pnl = position.calculate_unrealized_pnl(1900.0)
        assert unrealized_pnl == -50_000  # (1900 - 2000) * 500
        
        # クローズドポジション
        position.status = PositionStatus.CLOSED
        unrealized_pnl = position.calculate_unrealized_pnl(2100.0)
        assert unrealized_pnl == 0
    
    def test_position_to_dict(self):
        """ポジションの辞書変換"""
        position = Position(
            ticker="7203",
            status=PositionStatus.OPEN,
            entry_date=datetime(2023, 3, 28),
            entry_price=2000.0,
            total_shares=500,
            average_price=2000.0
        )
        
        position_dict = position.to_dict()
        
        assert position_dict['ticker'] == "7203"
        assert position_dict['status'] == "OPEN"
        assert position_dict['entry_date'] == "2023-03-28"
        assert position_dict['entry_price'] == 2000.0
        assert position_dict['total_shares'] == 500
