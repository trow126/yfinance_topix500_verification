#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yfinanceデータクライアント
株価データと配当データの取得・キャッシュ管理
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import pickle
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

from ..utils.logger import log
from ..utils.calendar import DividendDateCalculator, BusinessDayCalculator


class YFinanceClient:
    """yfinanceデータ取得クライアント"""
    
    def __init__(self, cache_dir: str = "./data/cache", cache_expire_hours: int = 24):
        """
        初期化
        
        Args:
            cache_dir: キャッシュディレクトリ
            cache_expire_hours: キャッシュ有効期限（時間）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_expire_hours = cache_expire_hours
        
        log.info(f"YFinanceClient initialized with cache_dir={cache_dir}")
    
    def get_price_data(self, 
                      ticker: str, 
                      start_date: str, 
                      end_date: str,
                      use_cache: bool = True) -> pd.DataFrame:
        """
        株価データを取得
        
        Args:
            ticker: 銘柄コード（4桁）
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
            use_cache: キャッシュを使用するか
            
        Returns:
            株価データ（OHLCV）
        """
        cache_key = f"price_{ticker}_{start_date}_{end_date}"
        
        # キャッシュチェック
        if use_cache:
            cached_data = self._load_cache(cache_key, 'price')
            if cached_data is not None:
                log.debug(f"Price data loaded from cache for {ticker}")
                return cached_data
        
        # yfinanceから取得
        try:
            yf_ticker = f"{ticker}.T"  # 東証の銘柄コード
            stock = yf.Ticker(yf_ticker)
            
            # 日足データを取得
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                log.warning(f"No price data found for {ticker}")
                return pd.DataFrame()
            
            # インデックスをタイムゾーンなしに変換
            hist.index = pd.to_datetime(hist.index).tz_localize(None)
            
            # 必要なカラムのみ保持
            price_data = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            
            # キャッシュに保存
            if use_cache:
                self._save_cache(cache_key, price_data, 'price')
            
            log.info(f"Price data fetched for {ticker}: {len(price_data)} records")
            return price_data
            
        except Exception as e:
            log.error(f"Error fetching price data for {ticker}: {str(e)}")
            return pd.DataFrame()
    
    def get_dividend_data(self, 
                         ticker: str,
                         use_cache: bool = True) -> pd.DataFrame:
        """
        配当データを取得し、権利確定日を計算
        
        Args:
            ticker: 銘柄コード（4桁）
            use_cache: キャッシュを使用するか
            
        Returns:
            配当データ（権利落ち日、権利確定日、配当金額）
        """
        cache_key = f"dividend_{ticker}"
        
        # キャッシュチェック
        if use_cache:
            cached_data = self._load_cache(cache_key, 'dividend')
            if cached_data is not None:
                log.debug(f"Dividend data loaded from cache for {ticker}")
                return cached_data
        
        # yfinanceから取得
        try:
            yf_ticker = f"{ticker}.T"
            stock = yf.Ticker(yf_ticker)
            
            # 配当履歴を取得
            dividends = stock.dividends
            
            if dividends.empty:
                log.warning(f"No dividend data found for {ticker}")
                return pd.DataFrame()
            
            # データフレームの作成
            dividend_data = pd.DataFrame({
                'ex_dividend_date': dividends.index.tz_localize(None),
                'dividend_amount': dividends.values
            })
            
            # 権利確定日を計算
            dividend_data['record_date'] = dividend_data['ex_dividend_date'].apply(
                lambda x: DividendDateCalculator.calculate_record_date(x.to_pydatetime())
            )
            
            # キャッシュに保存
            if use_cache:
                self._save_cache(cache_key, dividend_data, 'dividend')
            
            log.info(f"Dividend data fetched for {ticker}: {len(dividend_data)} records")
            return dividend_data
            
        except Exception as e:
            log.error(f"Error fetching dividend data for {ticker}: {str(e)}")
            return pd.DataFrame()
    
    def get_multiple_tickers_data(self,
                                tickers: List[str],
                                start_date: str,
                                end_date: str) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        複数銘柄のデータを一括取得
        
        Args:
            tickers: 銘柄コードリスト
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            銘柄ごとの価格・配当データ
        """
        results = {}
        
        for i, ticker in enumerate(tickers):
            log.info(f"Fetching data for {ticker} ({i+1}/{len(tickers)})")
            
            # 価格データ取得
            price_data = self.get_price_data(ticker, start_date, end_date)
            
            # 配当データ取得
            dividend_data = self.get_dividend_data(ticker)
            
            # 期間内の配当のみフィルタリング
            if not dividend_data.empty:
                mask = (dividend_data['ex_dividend_date'] >= pd.to_datetime(start_date)) & \
                       (dividend_data['ex_dividend_date'] <= pd.to_datetime(end_date))
                dividend_data = dividend_data[mask].copy()
            
            results[ticker] = {
                'price': price_data,
                'dividend': dividend_data
            }
        
        return results
    
    def _load_cache(self, cache_key: str, data_type: str) -> Optional[pd.DataFrame]:
        """
        キャッシュからデータを読み込む
        
        Args:
            cache_key: キャッシュキー
            data_type: データタイプ（price/dividend）
            
        Returns:
            キャッシュデータ（存在しないまたは期限切れの場合None）
        """
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        meta_file = self.cache_dir / f"{cache_key}.meta"
        
        if not cache_file.exists() or not meta_file.exists():
            return None
        
        # メタデータチェック
        with open(meta_file, 'r') as f:
            meta = json.load(f)
        
        # 有効期限チェック
        cached_time = datetime.fromisoformat(meta['timestamp'])
        if datetime.now() - cached_time > timedelta(hours=self.cache_expire_hours):
            log.debug(f"Cache expired for {cache_key}")
            return None
        
        # データ読み込み
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    
    def _save_cache(self, cache_key: str, data: pd.DataFrame, data_type: str) -> None:
        """
        データをキャッシュに保存
        
        Args:
            cache_key: キャッシュキー
            data: 保存するデータ
            data_type: データタイプ
        """
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        meta_file = self.cache_dir / f"{cache_key}.meta"
        
        # データ保存
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        
        # メタデータ保存
        meta = {
            'timestamp': datetime.now().isoformat(),
            'data_type': data_type,
            'records': len(data)
        }
        with open(meta_file, 'w') as f:
            json.dump(meta, f)
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        for file in self.cache_dir.glob("*"):
            file.unlink()
        log.info("Cache cleared")


# テスト用コード
if __name__ == "__main__":
    # クライアントの初期化
    client = YFinanceClient()
    
    # 単一銘柄のテスト
    ticker = "7203"  # トヨタ
    price_data = client.get_price_data(ticker, "2023-01-01", "2023-12-31")
    print(f"Price data shape: {price_data.shape}")
    print(price_data.head())
    
    dividend_data = client.get_dividend_data(ticker)
    print(f"\nDividend data shape: {dividend_data.shape}")
    print(dividend_data.tail())
