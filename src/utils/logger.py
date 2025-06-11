#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ロギングユーティリティ
システム全体で使用する統一的なロガーを提供
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


class BacktestLogger:
    """バックテスト用ロガー設定クラス"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """シングルトンパターンで初期化"""
        if not BacktestLogger._initialized:
            self.setup_logger()
            BacktestLogger._initialized = True
    
    def setup_logger(self, 
                     log_level: str = "INFO",
                     log_file: Optional[str] = None,
                     format_string: Optional[str] = None):
        """
        ロガーの設定
        
        Args:
            log_level: ログレベル
            log_file: ログファイルパス
            format_string: ログフォーマット
        """
        # 既存のハンドラーを削除
        logger.remove()
        
        # フォーマット設定
        if format_string is None:
            format_string = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        
        # コンソール出力の設定
        logger.add(
            sys.stdout,
            format=format_string,
            level=log_level,
            colorize=True
        )
        
        # ファイル出力の設定
        if log_file:
            # ログディレクトリの作成
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルハンドラーの追加
            logger.add(
                log_file,
                format=format_string,
                level=log_level,
                rotation="10 MB",  # 10MBでローテーション
                retention="30 days",  # 30日間保持
                compression="zip",  # 圧縮
                encoding="utf-8"
            )
    
    @staticmethod
    def get_logger():
        """ロガーインスタンスを取得"""
        return logger


# グローバルロガーインスタンスの作成
backtest_logger = BacktestLogger()
log = backtest_logger.get_logger()


# ログデコレーター
def log_execution(func):
    """関数の実行をログに記録するデコレーター"""
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        log.debug(f"Executing {func_name} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            log.debug(f"{func_name} completed successfully")
            return result
        except Exception as e:
            log.error(f"{func_name} failed with error: {str(e)}")
            raise
    return wrapper


# ログコンテキストマネージャー
class LogContext:
    """ログコンテキストマネージャー"""
    
    def __init__(self, context_name: str, level: str = "INFO"):
        self.context_name = context_name
        self.level = level
    
    def __enter__(self):
        log.log(self.level, f"Starting {self.context_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            log.log(self.level, f"Completed {self.context_name}")
        else:
            log.error(f"Failed {self.context_name}: {exc_val}")
        return False


# テスト用コード
if __name__ == "__main__":
    # ロガーのテスト
    log.info("This is an info message")
    log.warning("This is a warning message")
    log.error("This is an error message")
    
    # デコレーターのテスト
    @log_execution
    def test_function(x, y):
        return x + y
    
    result = test_function(10, 20)
    log.info(f"Result: {result}")
    
    # コンテキストマネージャーのテスト
    with LogContext("test operation"):
        log.info("Doing something...")
