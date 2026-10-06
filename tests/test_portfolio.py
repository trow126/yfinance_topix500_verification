#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポートフォリオのテスト
"""

import pytest
from datetime import datetime

from src.backtest.portfolio import Portfolio


class TestPortfolioMetrics:
    """パフォーマンス指標のテスト"""

    def test_avg_holding_days(self):
        """平均保有期間（暦日）"""
        portfolio = Portfolio(10_000_000)

        portfolio.execute_buy("7203", datetime(2023, 3, 28), 2000.0, 500, 550.0, "Entry")
        portfolio.execute_buy("6758", datetime(2023, 3, 28), 10000.0, 100, 550.0, "Entry")
        portfolio.mark_to_market(datetime(2023, 3, 28), {"7203": 2000.0, "6758": 10000.0})

        portfolio.execute_sell("7203", datetime(2023, 4, 5), 2100.0, 550.0, "Exit")   # 8日
        portfolio.execute_sell("6758", datetime(2023, 4, 11), 10500.0, 550.0, "Exit")  # 14日
        portfolio.mark_to_market(datetime(2023, 4, 11), {})

        metrics = portfolio.get_performance_metrics()

        assert metrics['avg_holding_days'] == pytest.approx(11.0)

    def test_avg_holding_days_no_closed_positions(self):
        """決済がない場合は0"""
        portfolio = Portfolio(10_000_000)
        portfolio.mark_to_market(datetime(2023, 3, 28), {})

        assert portfolio.get_performance_metrics()['avg_holding_days'] == 0.0
