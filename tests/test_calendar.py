#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
営業日計算のテスト
"""

import pytest
from datetime import datetime
from src.utils.calendar import BusinessDayCalculator, DividendDateCalculator


class TestBusinessDayCalculator:
    """営業日計算のテスト"""
    
    def test_is_business_day_weekday(self):
        """平日の判定"""
        # 2023年6月1日（木曜日）
        date = datetime(2023, 6, 1)
        assert BusinessDayCalculator.is_business_day(date) == True
    
    def test_is_business_day_weekend(self):
        """週末の判定"""
        # 2023年6月3日（土曜日）
        saturday = datetime(2023, 6, 3)
        assert BusinessDayCalculator.is_business_day(saturday) == False
        
        # 2023年6月4日（日曜日）
        sunday = datetime(2023, 6, 4)
        assert BusinessDayCalculator.is_business_day(sunday) == False
    
    def test_is_business_day_holiday(self):
        """祝日の判定"""
        # 2023年1月1日（元日）
        new_year = datetime(2023, 1, 1)
        assert BusinessDayCalculator.is_business_day(new_year) == False
        
        # 2023年5月3日（憲法記念日）
        holiday = datetime(2023, 5, 3)
        assert BusinessDayCalculator.is_business_day(holiday) == False
    
    def test_is_business_day_year_end(self):
        """年末年始の判定"""
        # 12月31日
        year_end = datetime(2023, 12, 31)
        assert BusinessDayCalculator.is_business_day(year_end) == False
        
        # 1月2日
        jan_2 = datetime(2023, 1, 2)
        assert BusinessDayCalculator.is_business_day(jan_2) == False
        
        # 1月3日
        jan_3 = datetime(2023, 1, 3)
        assert BusinessDayCalculator.is_business_day(jan_3) == False
    
    def test_add_business_days_positive(self):
        """営業日の加算（正の値）"""
        # 2023年6月1日（木曜日）から3営業日後
        start = datetime(2023, 6, 1)
        result = BusinessDayCalculator.add_business_days(start, 3)
        # 6月2日（金）、6月5日（月）、6月6日（火）
        assert result == datetime(2023, 6, 6)
    
    def test_add_business_days_negative(self):
        """営業日の加算（負の値）"""
        # 2023年6月6日（火曜日）から3営業日前
        start = datetime(2023, 6, 6)
        result = BusinessDayCalculator.add_business_days(start, -3)
        assert result == datetime(2023, 6, 1)
    
    def test_add_business_days_with_holiday(self):
        """祝日を挟む営業日計算"""
        # 2023年5月1日（月曜日）から3営業日後
        # 5月3日（水）は憲法記念日、5月4日（木）はみどりの日、5月5日（金）はこどもの日
        start = datetime(2023, 5, 1)
        result = BusinessDayCalculator.add_business_days(start, 3)
        # 5月2日（火）、5月8日（月）、5月9日（火）
        assert result == datetime(2023, 5, 9)
    
    def test_calculate_business_days(self):
        """営業日数の計算"""
        # 2023年6月1日（木）から6月6日（火）まで
        start = datetime(2023, 6, 1)
        end = datetime(2023, 6, 6)
        days = BusinessDayCalculator.calculate_business_days(start, end)
        assert days == 3  # 6月2日（金）、6月5日（月）、6月6日（火）


class TestDividendDateCalculator:
    """配当日計算のテスト"""
    
    def test_calculate_record_date(self):
        """権利確定日の計算"""
        # 2023年3月29日（水）が権利落ち日の場合
        ex_date = datetime(2023, 3, 29)
        record_date = DividendDateCalculator.calculate_record_date(ex_date)
        # T+2ルールで2営業日後の3月31日（金）が権利確定日
        assert record_date == datetime(2023, 3, 31)
    
    def test_calculate_record_date_with_weekend(self):
        """週末を挟む権利確定日の計算"""
        # 2023年6月29日（木）が権利落ち日の場合
        ex_date = datetime(2023, 6, 29)
        record_date = DividendDateCalculator.calculate_record_date(ex_date)
        # 6月30日（金）、7月3日（月）で2営業日後
        assert record_date == datetime(2023, 7, 3)
    
    def test_calculate_entry_date(self):
        """エントリー日の計算"""
        # 2023年3月31日（金）が権利確定日の場合
        record_date = datetime(2023, 3, 31)
        entry_date = DividendDateCalculator.calculate_entry_date(record_date, days_before=3)
        # 3営業日前は3月28日（火）
        assert entry_date == datetime(2023, 3, 28)
    
    def test_calculate_ex_dividend_date(self):
        """権利落ち日の計算"""
        # 2023年3月31日（金）が権利確定日の場合
        record_date = datetime(2023, 3, 31)
        ex_date = DividendDateCalculator.calculate_ex_dividend_date(record_date)
        # 2営業日前は3月29日（水）
        assert ex_date == datetime(2023, 3, 29)
