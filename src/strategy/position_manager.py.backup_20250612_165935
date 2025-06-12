#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポジション管理
個別銘柄のポジション管理と取引履歴の記録
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

from ..utils.logger import log


class PositionStatus(Enum):
    """ポジションステータス"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TradeType(Enum):
    """取引タイプ"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Trade:
    """取引記録"""
    ticker: str
    trade_type: TradeType
    date: datetime
    price: float
    shares: int
    commission: float
    amount: float  # 取引金額（手数料含む）
    reason: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class Position:
    """ポジション情報"""
    ticker: str
    status: PositionStatus
    entry_date: datetime
    entry_price: float
    total_shares: int
    average_price: float
    trades: List[Trade] = field(default_factory=list)
    
    # 配当関連情報
    ex_dividend_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
    dividend_amount: Optional[float] = None
    pre_ex_price: Optional[float] = None
    
    # 決済情報
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    # 損益情報
    realized_pnl: float = 0.0
    dividend_received: float = 0.0
    total_commission: float = 0.0
    
    def add_trade(self, trade: Trade) -> None:
        """
        取引を追加
        
        Args:
            trade: 取引記録
        """
        self.trades.append(trade)
        
        if trade.trade_type == TradeType.BUY:
            # 平均取得単価を更新
            total_cost = self.average_price * self.total_shares + trade.amount
            self.total_shares += trade.shares
            self.average_price = total_cost / self.total_shares if self.total_shares > 0 else 0
        else:
            # 売却の場合は株数を減少
            self.total_shares -= trade.shares
            if self.total_shares <= 0:
                self.status = PositionStatus.CLOSED
                self.exit_date = trade.date
                self.exit_price = trade.price
        
        # 手数料を累計
        self.total_commission += trade.commission
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        未実現損益を計算
        
        Args:
            current_price: 現在価格
            
        Returns:
            未実現損益
        """
        if self.status == PositionStatus.CLOSED or self.total_shares == 0:
            return 0.0
        
        market_value = current_price * self.total_shares
        cost_basis = self.average_price * self.total_shares
        return market_value - cost_basis
    
    def get_holding_days(self, current_date: datetime) -> int:
        """
        保有日数を取得
        
        Args:
            current_date: 現在日
            
        Returns:
            保有日数
        """
        end_date = self.exit_date if self.exit_date else current_date
        return (end_date - self.entry_date).days
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'ticker': self.ticker,
            'status': self.status.value,
            'entry_date': self.entry_date.strftime('%Y-%m-%d'),
            'entry_price': self.entry_price,
            'total_shares': self.total_shares,
            'average_price': self.average_price,
            'exit_date': self.exit_date.strftime('%Y-%m-%d') if self.exit_date else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'realized_pnl': self.realized_pnl,
            'dividend_received': self.dividend_received,
            'total_commission': self.total_commission,
            'trade_count': len(self.trades)
        }


class PositionManager:
    """ポジション管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.positions: Dict[str, Position] = {}  # ticker -> Position
        self.closed_positions: List[Position] = []
        self.all_trades: List[Trade] = []
        
        log.info("PositionManager initialized")
    
    def open_position(self,
                     ticker: str,
                     date: datetime,
                     price: float,
                     shares: int,
                     commission: float,
                     reason: str,
                     dividend_info: Optional[Dict] = None) -> Position:
        """
        新規ポジションを開く
        
        Args:
            ticker: 銘柄コード
            date: 取引日
            price: 取引価格
            shares: 株数
            commission: 手数料
            reason: 取引理由
            dividend_info: 配当情報
            
        Returns:
            作成されたポジション
        """
        if ticker in self.positions:
            raise ValueError(f"Position already exists for {ticker}")
        
        # 取引記録を作成
        amount = price * shares + commission
        trade = Trade(
            ticker=ticker,
            trade_type=TradeType.BUY,
            date=date,
            price=price,
            shares=shares,
            commission=commission,
            amount=amount,
            reason=reason
        )
        
        # ポジションを作成
        position = Position(
            ticker=ticker,
            status=PositionStatus.OPEN,
            entry_date=date,
            entry_price=price,
            total_shares=shares,
            average_price=price
        )
        
        # 配当情報を設定
        if dividend_info:
            position.ex_dividend_date = dividend_info.get('ex_dividend_date')
            position.record_date = dividend_info.get('record_date')
            position.dividend_amount = dividend_info.get('dividend_amount')
        
        # 取引を追加
        position.add_trade(trade)
        self.all_trades.append(trade)
        
        # ポジションを保存
        self.positions[ticker] = position
        
        log.info(f"Opened position: {ticker}, shares={shares}, price={price}")
        
        return position
    
    def add_to_position(self,
                       ticker: str,
                       date: datetime,
                       price: float,
                       shares: int,
                       commission: float,
                       reason: str) -> Position:
        """
        既存ポジションに追加
        
        Args:
            ticker: 銘柄コード
            date: 取引日
            price: 取引価格
            shares: 株数
            commission: 手数料
            reason: 取引理由
            
        Returns:
            更新されたポジション
        """
        if ticker not in self.positions:
            raise ValueError(f"No position exists for {ticker}")
        
        position = self.positions[ticker]
        
        # 取引記録を作成
        amount = price * shares + commission
        trade = Trade(
            ticker=ticker,
            trade_type=TradeType.BUY,
            date=date,
            price=price,
            shares=shares,
            commission=commission,
            amount=amount,
            reason=reason
        )
        
        # ポジションに追加
        position.add_trade(trade)
        self.all_trades.append(trade)
        
        log.info(f"Added to position: {ticker}, shares={shares}, price={price}")
        
        return position
    
    def close_position(self,
                      ticker: str,
                      date: datetime,
                      price: float,
                      commission: float,
                      reason: str) -> Position:
        """
        ポジションをクローズ
        
        Args:
            ticker: 銘柄コード
            date: 取引日
            price: 取引価格
            commission: 手数料
            reason: 取引理由
            
        Returns:
            クローズされたポジション
        """
        if ticker not in self.positions:
            raise ValueError(f"No position exists for {ticker}")
        
        position = self.positions[ticker]
        shares = position.total_shares
        
        # 取引記録を作成
        amount = price * shares - commission
        trade = Trade(
            ticker=ticker,
            trade_type=TradeType.SELL,
            date=date,
            price=price,
            shares=shares,
            commission=commission,
            amount=amount,
            reason=reason
        )
        
        # ポジションを更新
        position.add_trade(trade)
        position.exit_reason = reason
        self.all_trades.append(trade)
        
        # 実現損益を計算
        proceeds = price * shares - commission
        cost_basis = position.average_price * shares + position.total_commission
        position.realized_pnl = proceeds - cost_basis + position.dividend_received
        
        # クローズドポジションリストに移動
        self.closed_positions.append(position)
        del self.positions[ticker]
        
        log.info(f"Closed position: {ticker}, PnL={position.realized_pnl:.0f}")
        
        return position
    
    def update_dividend_received(self, ticker: str, dividend_per_share: float) -> None:
        """
        受取配当を更新
        
        Args:
            ticker: 銘柄コード
            dividend_per_share: 1株あたり配当
        """
        if ticker in self.positions:
            position = self.positions[ticker]
            position.dividend_received = dividend_per_share * position.total_shares
            log.info(f"Dividend received: {ticker}, amount={position.dividend_received:.0f}")
    
    def update_pre_ex_price(self, ticker: str, pre_ex_price: float) -> None:
        """
        権利落ち前日の価格を更新
        
        Args:
            ticker: 銘柄コード
            pre_ex_price: 権利落ち前日価格
        """
        if ticker in self.positions:
            self.positions[ticker].pre_ex_price = pre_ex_price
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """ポジションを取得"""
        return self.positions.get(ticker)
    
    def get_open_positions(self) -> List[Position]:
        """オープンポジションのリストを取得"""
        return list(self.positions.values())
    
    def get_position_count(self) -> int:
        """オープンポジション数を取得"""
        return len(self.positions)
    
    def get_total_market_value(self, prices: Dict[str, float]) -> float:
        """
        全ポジションの時価総額を計算
        
        Args:
            prices: 現在価格の辞書
            
        Returns:
            時価総額
        """
        total = 0.0
        for ticker, position in self.positions.items():
            if ticker in prices:
                total += prices[ticker] * position.total_shares
        return total
    
    def get_trades_dataframe(self) -> pd.DataFrame:
        """取引履歴をDataFrame形式で取得"""
        if not self.all_trades:
            return pd.DataFrame()
        
        trades_data = []
        for trade in self.all_trades:
            trades_data.append({
                'date': trade.date,
                'ticker': trade.ticker,
                'type': trade.trade_type.value,
                'price': trade.price,
                'shares': trade.shares,
                'amount': trade.amount,
                'commission': trade.commission,
                'reason': trade.reason
            })
        
        return pd.DataFrame(trades_data)
    
    def get_positions_summary(self) -> pd.DataFrame:
        """ポジションサマリーをDataFrame形式で取得"""
        all_positions = list(self.positions.values()) + self.closed_positions
        
        if not all_positions:
            return pd.DataFrame()
        
        positions_data = [pos.to_dict() for pos in all_positions]
        return pd.DataFrame(positions_data)


# テスト用コード
if __name__ == "__main__":
    # ポジション管理のテスト
    pm = PositionManager()
    
    # 新規ポジション
    dividend_info = {
        'ex_dividend_date': datetime(2023, 3, 29),
        'record_date': datetime(2023, 3, 31),
        'dividend_amount': 50.0
    }
    
    position = pm.open_position(
        ticker="7203",
        date=datetime(2023, 3, 28),
        price=2000.0,
        shares=500,
        commission=500.0,
        reason="Entry 3 days before record date",
        dividend_info=dividend_info
    )
    
    print(f"Position opened: {position.ticker}")
    print(f"Total shares: {position.total_shares}")
    print(f"Average price: {position.average_price}")
    
    # ポジション追加
    pm.add_to_position(
        ticker="7203",
        date=datetime(2023, 3, 29),
        price=1950.0,
        shares=300,
        commission=300.0,
        reason="Add on ex-dividend drop"
    )
    
    print(f"\nAfter addition:")
    print(f"Total shares: {position.total_shares}")
    print(f"Average price: {position.average_price}")
