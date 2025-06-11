#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
営業日計算ユーティリティ
日本の営業日を考慮した日付計算を提供
"""

from datetime import datetime, timedelta
from typing import List, Optional
import jpholiday
import pandas as pd


class BusinessDayCalculator:
    """営業日計算クラス"""
    
    @staticmethod
    def is_business_day(date: datetime) -> bool:
        """
        指定された日付が営業日かどうかを判定
        
        Args:
            date: 判定する日付
            
        Returns:
            営業日の場合True
        """
        # 土日の判定
        if date.weekday() >= 5:
            return False
        
        # 日本の祝日判定
        if jpholiday.is_holiday(date):
            return False
        
        # 年末年始の特別休場（12/31, 1/1, 1/2, 1/3）
        if date.month == 12 and date.day == 31:
            return False
        if date.month == 1 and date.day in [1, 2, 3]:
            return False
        
        return True
    
    @staticmethod
    def add_business_days(start_date: datetime, days: int) -> datetime:
        """
        指定された日付から営業日ベースで日数を加算
        
        Args:
            start_date: 開始日
            days: 加算する営業日数（負の値も可）
            
        Returns:
            計算後の日付
        """
        current_date = start_date
        days_to_add = abs(days)
        direction = 1 if days >= 0 else -1
        
        while days_to_add > 0:
            current_date += timedelta(days=direction)
            if BusinessDayCalculator.is_business_day(current_date):
                days_to_add -= 1
        
        return current_date
    
    @staticmethod
    def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
        """
        2つの日付間の営業日数を計算
        
        Args:
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            営業日数
        """
        if start_date > end_date:
            start_date, end_date = end_date, start_date
            sign = -1
        else:
            sign = 1
        
        business_days = 0
        current_date = start_date
        
        while current_date < end_date:
            current_date += timedelta(days=1)
            if BusinessDayCalculator.is_business_day(current_date):
                business_days += 1
        
        return business_days * sign
    
    @staticmethod
    def get_business_days_list(start_date: datetime, end_date: datetime) -> List[datetime]:
        """
        指定期間内の営業日リストを取得
        
        Args:
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            営業日のリスト
        """
        business_days = []
        current_date = start_date
        
        while current_date <= end_date:
            if BusinessDayCalculator.is_business_day(current_date):
                business_days.append(current_date)
            current_date += timedelta(days=1)
        
        return business_days


class DividendDateCalculator:
    """配当権利日計算クラス（既存コードから移植）"""
    
    @staticmethod
    def calculate_record_date(ex_dividend_date: datetime) -> datetime:
        """
        権利落ち日から権利確定日を計算（T+2ルール）
        
        Args:
            ex_dividend_date: 権利落ち日
            
        Returns:
            権利確定日
        """
        # T+2ルールで2営業日後が権利確定日
        return BusinessDayCalculator.add_business_days(ex_dividend_date, 2)
    
    @staticmethod
    def calculate_entry_date(record_date: datetime, days_before: int = 3) -> datetime:
        """
        権利確定日からエントリー日を計算
        
        Args:
            record_date: 権利確定日
            days_before: 何営業日前にエントリーするか
            
        Returns:
            エントリー日
        """
        return BusinessDayCalculator.add_business_days(record_date, -days_before)
    
    @staticmethod
    def calculate_ex_dividend_date(record_date: datetime) -> datetime:
        """
        権利確定日から権利落ち日を計算
        
        Args:
            record_date: 権利確定日
            
        Returns:
            権利落ち日
        """
        # 権利確定日の2営業日前が権利落ち日
        return BusinessDayCalculator.add_business_days(record_date, -2)


def create_trading_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """
    指定期間の取引日カレンダーを作成
    
    Args:
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        
    Returns:
        取引日のDatetimeIndex
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # 営業日リストを取得
    business_days = BusinessDayCalculator.get_business_days_list(
        start.to_pydatetime(), 
        end.to_pydatetime()
    )
    
    # DatetimeIndexに変換
    return pd.DatetimeIndex(business_days)


# テスト用コード
if __name__ == "__main__":
    # 営業日計算のテスト
    test_date = datetime(2023, 12, 29)  # 金曜日
    print(f"{test_date.strftime('%Y-%m-%d')}は営業日: {BusinessDayCalculator.is_business_day(test_date)}")
    
    # 営業日加算のテスト
    next_bd = BusinessDayCalculator.add_business_days(test_date, 3)
    print(f"3営業日後: {next_bd.strftime('%Y-%m-%d')}")
    
    # 権利日計算のテスト
    ex_date = datetime(2023, 3, 29)
    record_date = DividendDateCalculator.calculate_record_date(ex_date)
    print(f"権利落ち日: {ex_date.strftime('%Y-%m-%d')} → 権利確定日: {record_date.strftime('%Y-%m-%d')}")
    
    entry_date = DividendDateCalculator.calculate_entry_date(record_date)
    print(f"エントリー日: {entry_date.strftime('%Y-%m-%d')}")
