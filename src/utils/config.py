#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定管理ユーティリティ
YAMLファイルから設定を読み込み、アプリケーション全体で使用
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BacktestConfig:
    """バックテスト設定"""
    start_date: str
    end_date: str
    initial_capital: float


@dataclass
class DataSourceConfig:
    """データソース設定"""
    primary: str
    cache_dir: str
    cache_expire_hours: int = 24


@dataclass
class EntryConfig:
    """エントリー設定"""
    days_before_record: int
    position_size: float
    max_positions: int = 10


@dataclass
class AdditionConfig:
    """買い増し設定"""
    enabled: bool
    add_ratio: float
    add_on_drop: bool = True


@dataclass
class ExitConfig:
    """決済設定"""
    max_holding_days: int
    stop_loss_pct: float
    take_profit_on_window_fill: bool = True


@dataclass
class StrategyConfig:
    """戦略設定"""
    entry: EntryConfig
    addition: AdditionConfig
    exit: ExitConfig


@dataclass
class ExecutionConfig:
    """執行設定"""
    slippage: float
    commission: float
    min_commission: float = 100
    slippage_ex_date: float = 0.005  # 権利落ち日前後のスリッページ
    max_commission: float = 1100  # 上限手数料
    tax_rate: float = 0.20315  # 配当課税率


@dataclass
class UniverseConfig:
    """銘柄ユニバース設定"""
    tickers: list = field(default_factory=list)


@dataclass
class LoggingConfig:
    """ロギング設定"""
    level: str
    file: str
    format: str


@dataclass
class OutputConfig:
    """出力設定"""
    results_dir: str
    report_format: list
    save_trades: bool = True
    save_portfolio_history: bool = True


@dataclass
class Config:
    """全体設定"""
    backtest: BacktestConfig
    data_source: DataSourceConfig
    strategy: StrategyConfig
    execution: ExecutionConfig
    universe: UniverseConfig
    logging: LoggingConfig
    output: OutputConfig


class ConfigLoader:
    """設定ファイルローダー"""
    
    @staticmethod
    def load_config(config_path: str) -> Config:
        """
        YAMLファイルから設定を読み込む
        
        Args:
            config_path: 設定ファイルパス
            
        Returns:
            設定オブジェクト
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        # 環境変数の展開
        config_dict = ConfigLoader._expand_env_vars(config_dict)
        
        # 設定オブジェクトの作成
        return ConfigLoader._create_config_object(config_dict)
    
    @staticmethod
    def _expand_env_vars(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        設定値中の環境変数を展開
        
        Args:
            config_dict: 設定辞書
            
        Returns:
            環境変数展開後の設定辞書
        """
        def expand_value(value):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                return os.environ.get(env_var, value)
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(v) for v in value]
            else:
                return value
        
        return expand_value(config_dict)
    
    @staticmethod
    def _create_config_object(config_dict: Dict[str, Any]) -> Config:
        """
        辞書から設定オブジェクトを作成
        
        Args:
            config_dict: 設定辞書
            
        Returns:
            設定オブジェクト
        """
        # バックテスト設定
        backtest_config = BacktestConfig(**config_dict['backtest'])
        
        # データソース設定
        data_source_config = DataSourceConfig(**config_dict['data_source'])
        
        # 戦略設定
        strategy_dict = config_dict['strategy']
        entry_config = EntryConfig(**strategy_dict['entry'])
        addition_config = AdditionConfig(**strategy_dict['addition'])
        exit_config = ExitConfig(**strategy_dict['exit'])
        strategy_config = StrategyConfig(entry_config, addition_config, exit_config)
        
        # 執行設定
        execution_config = ExecutionConfig(**config_dict['execution'])
        
        # ユニバース設定
        universe_config = UniverseConfig(**config_dict['universe'])
        
        # ロギング設定
        logging_config = LoggingConfig(**config_dict['logging'])
        
        # 出力設定
        output_config = OutputConfig(**config_dict['output'])
        
        return Config(
            backtest=backtest_config,
            data_source=data_source_config,
            strategy=strategy_config,
            execution=execution_config,
            universe=universe_config,
            logging=logging_config,
            output=output_config
        )
    
    @staticmethod
    def save_config(config: Config, output_path: str) -> None:
        """
        設定オブジェクトをYAMLファイルに保存
        
        Args:
            config: 設定オブジェクト
            output_path: 出力パス
        """
        # データクラスを辞書に変換
        import dataclasses
        config_dict = dataclasses.asdict(config)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)


def load_config(config_path: str = "config/config.yaml") -> Config:
    """
    設定ファイルを読み込む便利関数
    
    Args:
        config_path: 設定ファイルパス
        
    Returns:
        設定オブジェクト
    """
    return ConfigLoader.load_config(config_path)


# テスト用コード
if __name__ == "__main__":
    # 設定ファイルの読み込みテスト
    try:
        config = load_config("../../config/config.yaml")
        print(f"Start date: {config.backtest.start_date}")
        print(f"End date: {config.backtest.end_date}")
        print(f"Initial capital: {config.backtest.initial_capital:,}")
        print(f"Position size: {config.strategy.entry.position_size:,}")
        print(f"Tickers: {config.universe.tickers}")
    except Exception as e:
        print(f"Error loading config: {e}")
