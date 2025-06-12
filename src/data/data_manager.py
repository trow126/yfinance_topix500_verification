#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データマネージャー
各種データソースを統合的に管理し、バックテストエンジンに提供
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from .yfinance_client import YFinanceClient
from ..utils.logger import log
from ..utils.config import DataSourceConfig


class DataManager:
    """データ管理クラス"""
    
    def __init__(self, config: DataSourceConfig):
        """
        初期化
        
        Args:
            config: データソース設定
        """
        self.config = config
        
        # データソースの初期化
        if config.primary == "yfinance":
            self.client = YFinanceClient(
                cache_dir=config.cache_dir,
                cache_expire_hours=config.cache_expire_hours
            )
        else:
            raise ValueError(f"Unsupported data source: {config.primary}")
        
        # データキャッシュ
        self._price_data_cache: Dict[str, pd.DataFrame] = {}
        self._dividend_data_cache: Dict[str, pd.DataFrame] = {}
        
        log.info(f"DataManager initialized with {config.primary}")
    
    def load_data(self, 
                 tickers: List[str], 
                 start_date: str, 
                 end_date: str) -> None:
        """
        指定銘柄のデータを一括ロード
        
        Args:
            tickers: 銘柄コードリスト
            start_date: 開始日
            end_date: 終了日
        """
        log.info(f"Loading data for {len(tickers)} tickers from {start_date} to {end_date}")
        
        # データ取得
        data = self.client.get_multiple_tickers_data(tickers, start_date, end_date)
        
        # キャッシュに格納
        for ticker, ticker_data in data.items():
            self._price_data_cache[ticker] = ticker_data['price']
            self._dividend_data_cache[ticker] = ticker_data['dividend']
        
        log.info("Data loading completed")
    
    def get_price_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        指定銘柄の全価格データを取得
        
        Args:
            ticker: 銘柄コード
            
        Returns:
            価格データ（データがない場合None）
        """
        if ticker not in self._price_data_cache:
            log.warning(f"No price data cached for {ticker}")
            return None
        
        return self._price_data_cache[ticker]
    
    def get_price_on_date(self, 
                         ticker: str, 
                         date: datetime,
                         price_type: str = 'Close') -> Optional[float]:
        """
        特定日の株価を取得
        
        Args:
            ticker: 銘柄コード
            date: 取得日
            price_type: 価格タイプ（Open/High/Low/Close）
            
        Returns:
            株価（データがない場合None）
        """
        if ticker not in self._price_data_cache:
            log.warning(f"No price data cached for {ticker}")
            return None
        
        price_data = self._price_data_cache[ticker]
        
        # 日付でフィルタ
        date_str = date.strftime('%Y-%m-%d')
        if date_str in price_data.index:
            return float(price_data.loc[date_str, price_type])
        
        # 直近の営業日のデータを使用
        mask = price_data.index <= date_str
        if mask.any():
            return float(price_data[mask].iloc[-1][price_type])
        
        return None
    
    def get_price_range(self,
                       ticker: str,
                       start_date: datetime,
                       end_date: datetime) -> pd.DataFrame:
        """
        期間内の価格データを取得
        
        Args:
            ticker: 銘柄コード
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            価格データ
        """
        if ticker not in self._price_data_cache:
            log.warning(f"No price data cached for {ticker}")
            return pd.DataFrame()
        
        price_data = self._price_data_cache[ticker]
        
        # 期間でフィルタ
        mask = (price_data.index >= start_date.strftime('%Y-%m-%d')) & \
               (price_data.index <= end_date.strftime('%Y-%m-%d'))
        
        return price_data[mask].copy()
    
    def get_dividends_in_period(self,
                              ticker: str,
                              start_date: datetime,
                              end_date: datetime) -> pd.DataFrame:
        """
        期間内の配当データを取得
        
        Args:
            ticker: 銘柄コード
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            配当データ
        """
        if ticker not in self._dividend_data_cache:
            log.warning(f"No dividend data cached for {ticker}")
            return pd.DataFrame()
        
        dividend_data = self._dividend_data_cache[ticker]
        
        if dividend_data.empty:
            return pd.DataFrame()
        
        # 期間でフィルタ（権利確定日ベース）
        mask = (dividend_data['record_date'] >= pd.Timestamp(start_date)) & \
               (dividend_data['record_date'] <= pd.Timestamp(end_date))
        
        return dividend_data[mask].copy()
    
    def get_next_dividend(self,
                         ticker: str,
                         current_date: datetime) -> Optional[Dict]:
        """
        次の配当情報を取得
        
        Args:
            ticker: 銘柄コード
            current_date: 基準日
            
        Returns:
            次の配当情報（ない場合None）
        """
        if ticker not in self._dividend_data_cache:
            return None
        
        dividend_data = self._dividend_data_cache[ticker]
        
        if dividend_data.empty:
            return None
        
        # 未来の配当をフィルタ
        future_dividends = dividend_data[
            dividend_data['record_date'] > pd.Timestamp(current_date)
        ].sort_values('record_date')
        
        if future_dividends.empty:
            return None
        
        # 最も近い配当
        next_div = future_dividends.iloc[0]
        
        return {
            'ex_dividend_date': next_div['ex_dividend_date'].to_pydatetime(),
            'record_date': next_div['record_date'].to_pydatetime(),
            'dividend_amount': float(next_div['dividend_amount'])
        }
    
    def calculate_returns(self,
                         ticker: str,
                         start_date: datetime,
                         end_date: datetime,
                         include_dividends: bool = True) -> float:
        """
        期間リターンを計算
        
        Args:
            ticker: 銘柄コード
            start_date: 開始日
            end_date: 終了日
            include_dividends: 配当を含めるか
            
        Returns:
            リターン率
        """
        # 開始価格
        start_price = self.get_price_on_date(ticker, start_date)
        if start_price is None:
            return 0.0
        
        # 終了価格
        end_price = self.get_price_on_date(ticker, end_date)
        if end_price is None:
            return 0.0
        
        # 価格リターン
        price_return = (end_price - start_price) / start_price
        
        # 配当リターン
        dividend_return = 0.0
        if include_dividends:
            dividends = self.get_dividends_in_period(ticker, start_date, end_date)
            if not dividends.empty:
                total_dividends = dividends['dividend_amount'].sum()
                dividend_return = total_dividends / start_price
        
        return price_return + dividend_return
    
    def get_universe_data(self, date: datetime) -> List[str]:
        """
        指定日のユニバース（取引可能銘柄）を取得
        
        Args:
            date: 基準日
            
        Returns:
            銘柄コードリスト
        """
        # 現在はキャッシュされた全銘柄を返す
        # 将来的には構成銘柄の変更に対応
        return list(self._price_data_cache.keys())
    
    def validate_data(self) -> Dict[str, List[str]]:
        """
        データの検証
        
        Returns:
            検証結果（エラー・警告のリスト）
        """
        errors = []
        warnings = []
        
        # 価格データの検証
        for ticker, price_data in self._price_data_cache.items():
            if price_data.empty:
                errors.append(f"{ticker}: No price data")
                continue
            
            # 欠損値チェック
            null_count = price_data.isnull().sum().sum()
            if null_count > 0:
                warnings.append(f"{ticker}: {null_count} null values in price data")
            
            # 異常値チェック（前日比50%以上）
            returns = price_data['Close'].pct_change()
            extreme_moves = returns[returns.abs() > 0.5]
            if len(extreme_moves) > 0:
                warnings.append(f"{ticker}: {len(extreme_moves)} extreme price moves (>50%)")
        
        # 配当データの検証
        for ticker, dividend_data in self._dividend_data_cache.items():
            if dividend_data.empty:
                warnings.append(f"{ticker}: No dividend data")
        
        return {
            'errors': errors,
            'warnings': warnings
        }


# テスト用コード
if __name__ == "__main__":
    from ..utils.config import DataSourceConfig
    
    # 設定
    config = DataSourceConfig(
        primary="yfinance",
        cache_dir="./data/cache",
        cache_expire_hours=24
    )
    
    # データマネージャーの初期化
    dm = DataManager(config)
    
    # データロード
    tickers = ["7203", "6758"]
    dm.load_data(tickers, "2023-01-01", "2023-12-31")
    
    # データ検証
    validation = dm.validate_data()
    print(f"Errors: {validation['errors']}")
    print(f"Warnings: {validation['warnings']}")
    
    # 価格取得テスト
    price = dm.get_price_on_date("7203", datetime(2023, 6, 1))
    print(f"Price on 2023-06-01: {price}")
