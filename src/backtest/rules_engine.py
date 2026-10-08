#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ルール型戦略の汎用バックテストエンジン（税引後・コスト込み・待機資金は 1306）

調査指示書（docs/research/beat_index_brief.md）4 章の基準に合わせた共通の土台:
- 売却益・配当に 20.315% を課税（売るたびに課税、損益通算は同一年内のみ。src/backtest/tax.py）
- スリッページは売買代金 10 億円/日以上の銘柄は片道 0.1%、それ未満は 0.3%
- 手数料は 0 円（楽天ゼロコース）。2023 年 10 月より前も 0 円として扱う（結果に明記すること）
- 使っていない現金は 1306 で持ち、株を買うときに必要な分だけ売る（ETF の売却益にも課税）
- 期末には株も ETF も全部売ったとみなして課税し、税引後の最終評価額で比較する

戦略は Strategy プロトコルを実装する: 毎営業日 orders() が呼ばれ、
売る銘柄と買う銘柄（金額）を返す。何もしない日は None を返す。
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Protocol

import numpy as np
import pandas as pd

from ..strategy.monthly_rights import MarketPanel
from .benchmark import annualized, buy_and_hold, max_drawdown
from .tax import CapitalGainsTax


@dataclass
class ExecutionConfig:
    slippage_liquid: float = 0.001          # 売買代金 10 億円/日以上
    slippage_illiquid: float = 0.003        # それ未満
    liquid_turnover: float = 1_000_000_000
    commission: float = 0.0
    tax_rate: float = 0.20315
    etf_slippage: float = 0.0005
    lot: int = 100


@dataclass
class RulesConfig:
    start_date: str = "2019-01-01"
    end_date: str = "2025-12-31"
    initial_capital: float = 15_000_000
    sweep_ticker: str = "1306"              # 空なら現金のまま
    cash_buffer: float = 0.0
    liquidate_at_end: bool = True
    # 約定のタイミング（第 2 期: docs/research/hypotheses.md 3d 章）
    # exec_delay: 判断日（orders() が呼ばれた日）の何営業日後に約定するか。0 = 判断日の当日（第 1 期）
    # exec_price: "close"（終値）/ "open"（始値。待機資金の 1306 も始値で売買する）
    exec_delay: int = 0
    exec_price: str = "close"
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


@dataclass
class Holding:
    code: str
    shares: int
    avg_price: float
    entry_date: pd.Timestamp
    meta: dict = field(default_factory=dict)

    @property
    def cost(self) -> float:
        return self.shares * self.avg_price


@dataclass
class Orders:
    sells: List[str] = field(default_factory=list)       # 全株売る銘柄
    buys: Dict[str, float] = field(default_factory=dict)  # 銘柄 → 買う金額（円）
    reason: str = ""
    meta: Dict[str, dict] = field(default_factory=dict)   # 銘柄 → 保有に付けるメモ


class Strategy(Protocol):
    name: str

    def orders(self, date: pd.Timestamp, panel: MarketPanel,
               holdings: Dict[str, Holding], equity: float) -> Optional[Orders]: ...


class RulesEngine:
    def __init__(self, config: RulesConfig, strategy: Strategy, panel: MarketPanel,
                 etf: Optional[pd.DataFrame] = None):
        self.config = config
        self.strategy = strategy
        self.panel = panel
        x = config.execution
        self.tax = CapitalGainsTax(rate=x.tax_rate)

        start, end = pd.Timestamp(config.start_date), pd.Timestamp(config.end_date)
        cal = panel.calendar
        self.trading_days = cal[(cal >= start) & (cal <= end)]
        if len(self.trading_days) == 0:
            raise ValueError("期間に営業日がありません")

        self.cash = float(config.initial_capital)
        self.holdings: Dict[str, Holding] = {}
        self.etf_units = 0.0
        self.etf_avg = 0.0
        self.etf_close = self.etf_dist = None
        if config.sweep_ticker:
            if etf is None:
                raise ValueError("sweep_ticker を使うには etf データが必要です")
            self.etf_close = etf["Close"].reindex(cal).ffill()
            self.etf_dist = etf["Dividends"].reindex(cal).fillna(0.0)
        self.etf_raw = etf
        if config.exec_price not in ("close", "open"):
            raise ValueError(f"exec_price は close / open: {config.exec_price}")
        if config.exec_price == "open" and config.sweep_ticker:
            self.etf_open = etf["Open"].reindex(cal)
        else:
            self.etf_open = None
        self.pending: Dict[int, List[tuple]] = {}  # 約定する営業日の番号 → [(判断日, Orders)]

        ev = panel.events.set_index(["ex_date", "code"])["dividend"]
        self.dividends_by_date = {d: g.droplevel(0).to_dict() for d, g in ev.groupby(level=0)}

        self.trades: List[dict] = []
        self.closed: List[dict] = []
        self.history: List[dict] = []
        self.dividends_after_tax = 0.0
        self.commission_paid = 0.0
        self.skipped: List[dict] = []
        self._trading_open = False

    # ------------------------------------------------------------------ helpers
    def _slippage(self, code: str, date: pd.Timestamp) -> float:
        x = self.config.execution
        t = self.panel.avg_turnover.at[date, code] if code in self.panel.avg_turnover.columns else np.nan
        return x.slippage_liquid if (pd.notna(t) and t >= x.liquid_turnover) else x.slippage_illiquid

    def _commission(self, amount: float) -> float:
        return amount * self.config.execution.commission

    def _etf_price(self, date) -> Optional[float]:
        if self.etf_close is None:
            return None
        p = self.etf_close.get(date)
        return None if p is None or pd.isna(p) else float(p)

    def _etf_trade_price(self, date) -> Optional[float]:
        """ETF を売買する価格（始値約定なら始値。無ければ終値）"""
        if self.etf_open is not None and self._trading_open:
            p = self.etf_open.get(date)
            if p is not None and pd.notna(p):
                return float(p)
        return self._etf_price(date)

    def _trade_price(self, code: str, date: pd.Timestamp) -> Optional[float]:
        if self._trading_open:
            p = self.panel.open_price(code, date)
            if p is not None:
                return p
            # 始値が無い（寄らなかった）日は終値で約定したとみなす
        return self.panel.price(code, date)

    def _buy_etf(self, amount: float, date) -> None:
        price = self._etf_price(date)
        if not price or amount <= 0:
            return
        fill = price * (1 + self.config.execution.etf_slippage)
        units = amount / fill
        self.etf_avg = (self.etf_avg * self.etf_units + fill * units) / (self.etf_units + units)
        self.etf_units += units
        self.cash -= amount

    def _sell_etf(self, amount: float, date, all_units: bool = False) -> float:
        """現金が amount 足りないとき（または全部）ETF を売る。売却益には課税。得た現金を返す"""
        price = self._etf_trade_price(date)
        if not price or self.etf_units <= 0:
            return 0.0
        fill = price * (1 - self.config.execution.etf_slippage)
        # 売却益の税を引いた後に amount が手に入るように口数を決める
        net_per_unit = fill - self.tax.rate * max(fill - self.etf_avg, 0.0)
        units = self.etf_units if all_units else min(amount / net_per_unit, self.etf_units)
        proceeds = units * fill
        pnl = (fill - self.etf_avg) * units
        tax = self.tax.on_sale(date, pnl)
        self.etf_units -= units
        if self.etf_units < 1e-9:
            self.etf_units, self.etf_avg = 0.0, 0.0
        self.cash += proceeds - tax
        self.trades.append({"date": date, "code": self.config.sweep_ticker, "side": "SELL", "shares": units,
                            "price": fill, "amount": proceeds, "pnl": pnl, "tax": tax, "reason": "ETF (sweep)"})
        return proceeds - tax

    def _lot(self, code: str, date: pd.Timestamp) -> int:
        """その日の単元（yfinance の価格は後の分割で遡及調整されているので補正）"""
        f = self.panel.split_factor.at[date, code] if code in self.panel.split_factor.columns else 1.0
        return max(1, int(round(self.config.execution.lot * (f if pd.notna(f) else 1.0))))

    def _buy(self, code: str, date: pd.Timestamp, yen: float, reason: str, meta: dict) -> bool:
        price = self._trade_price(code, date)
        if price is None or yen <= 0:
            return False
        fill = price * (1 + self._slippage(code, date))
        lot = self._lot(code, date)
        shares = int(yen // (fill * lot)) * lot
        if shares <= 0:
            self.skipped.append({"date": date, "code": code, "reason": "単元に満たない", "yen": yen})
            return False
        commission = self._commission(fill * shares)
        need = fill * shares + commission
        for _ in range(2):  # 年内の損益通算で税額がずれることがあるので、足りなければもう一度売る
            if need > self.cash:
                self._sell_etf(need - self.cash + 1, date)
        if need > self.cash + 1e-6:
            self.skipped.append({"date": date, "code": code, "reason": "資金不足", "yen": need})
            return False
        self.cash -= need
        self.commission_paid += commission
        h = self.holdings.get(code)
        if h:
            h.avg_price = (h.avg_price * h.shares + fill * shares) / (h.shares + shares)
            h.shares += shares
            h.meta.update(meta or {})
        else:
            self.holdings[code] = Holding(code, shares, fill, date, dict(meta or {}))
        self.trades.append({"date": date, "code": code, "side": "BUY", "shares": shares, "price": fill,
                            "amount": fill * shares, "pnl": 0.0, "tax": 0.0, "reason": reason})
        return True

    def _sell(self, code: str, date: pd.Timestamp, reason: str) -> bool:
        h = self.holdings.get(code)
        price = self._trade_price(code, date)
        if h is None:
            return False
        if price is None:
            price = self.panel.valuation_prices(date).get(code)  # 値が付かない日は直近終値で売ったとみなす
            if price is None:
                return False
        fill = price * (1 - self._slippage(code, date))
        commission = self._commission(fill * h.shares)
        proceeds = fill * h.shares - commission
        pnl = proceeds - h.cost
        tax = self.tax.on_sale(date, pnl)
        self.cash += proceeds - tax
        self.commission_paid += commission
        self.trades.append({"date": date, "code": code, "side": "SELL", "shares": h.shares, "price": fill,
                            "amount": fill * h.shares, "pnl": pnl, "tax": tax, "reason": reason})
        self.closed.append({"code": code, "entry_date": h.entry_date, "exit_date": date, "shares": h.shares,
                            "avg_price": h.avg_price, "exit_price": fill, "pnl": pnl, "tax": tax,
                            "holding_days": (date - h.entry_date).days, "reason": reason, **h.meta})
        del self.holdings[code]
        return True

    def _execute(self, orders: Orders, date: pd.Timestamp, signal_date: pd.Timestamp) -> None:
        for code in orders.sells:
            self._sell(code, date, orders.reason)
        for code, yen in orders.buys.items():
            meta = dict(orders.meta.get(code, {}))
            meta.setdefault("signal_date", signal_date)
            self._buy(code, date, yen, orders.reason, meta)

    def _stock_value(self, date) -> float:
        if not self.holdings:
            return 0.0
        prices = self.panel.valuation_prices(date)
        return float(sum(h.shares * prices.get(c, h.avg_price) for c, h in self.holdings.items()))

    # ------------------------------------------------------------------ main loop
    def run(self) -> Dict:
        for i, date in enumerate(self.trading_days):
            # 0. ETF の分配金（税引後で現金に）
            if self.etf_dist is not None and self.etf_units > 0:
                d = float(self.etf_dist.get(date, 0.0))
                if d > 0:
                    gross = self.etf_units * d
                    net = gross - self.tax.on_dividend(date, gross)
                    self.cash += net
                    self.dividends_after_tax += net
            # 1. 株の配当（権利落ち日に前日保有株数で。税引後）
            for code, div in self.dividends_by_date.get(date, {}).items():
                h = self.holdings.get(code)
                if h:
                    gross = h.shares * div
                    net = gross - self.tax.on_dividend(date, gross)
                    self.cash += net
                    self.dividends_after_tax += net
            # 2. 前の営業日までに決めた注文の約定（exec_delay >= 1）→ 戦略の注文
            self._trading_open = self.config.exec_price == "open"
            for signal_date, queued in self.pending.pop(i, []):
                self._execute(queued, date, signal_date)
            equity = self.cash + self._stock_value(date) + self.etf_units * (self._etf_price(date) or 0.0)
            orders = self.strategy.orders(date, self.panel, self.holdings, equity)
            if orders:
                if self.config.exec_delay <= 0:
                    self._execute(orders, date, date)
                else:  # 期末を過ぎる注文は約定しない（期末清算に任せる）
                    self.pending.setdefault(i + self.config.exec_delay, []).append((date, orders))
            self._trading_open = False  # 期末清算と待機資金の買いは終値
            # 3. 期末の清算
            last = i == len(self.trading_days) - 1
            if last and self.config.liquidate_at_end:
                for code in list(self.holdings):
                    self._sell(code, date, "Liquidate at end")
                self._sell_etf(0.0, date, all_units=True)
            # 4. 余った現金を ETF へ
            if not last or not self.config.liquidate_at_end:
                excess = self.cash - self.config.cash_buffer
                if excess > 0:
                    self._buy_etf(excess, date)
            # 5. 時価評価
            stock_value = self._stock_value(date)
            etf_value = self.etf_units * (self._etf_price(date) or 0.0)
            self.history.append({"date": date, "cash": self.cash, "stock_value": stock_value,
                                 "etf_value": etf_value, "total_value": self.cash + stock_value + etf_value,
                                 "positions": len(self.holdings)})
        return self._results()

    # ------------------------------------------------------------------ results
    def _results(self) -> Dict:
        history = pd.DataFrame(self.history).set_index("date")
        values = history["total_value"]
        initial = self.config.initial_capital
        final = float(values.iloc[-1])
        trades = pd.DataFrame(self.trades)
        closed = pd.DataFrame(self.closed)
        stock_trades = trades[trades["code"] != self.config.sweep_ticker] if len(trades) else trades
        years = (values.index[-1] - values.index[0]).days / 365.25
        ann = annualized(values)

        bench = None
        if self.etf_raw is not None:
            bench = buy_and_hold(self.etf_raw, str(self.trading_days[0].date()), str(self.trading_days[-1].date()),
                                 initial, tax_rate=self.config.execution.tax_rate,
                                 slippage=self.config.execution.etf_slippage, calendar=self.trading_days)
        metrics = {
            "strategy": getattr(self.strategy, "name", type(self.strategy).__name__),
            "start": str(self.trading_days[0].date()), "end": str(self.trading_days[-1].date()),
            "initial_capital": initial,
            "final_value_after_tax": final,
            "profit_after_tax": final - initial,
            "benchmark_final_after_tax": bench.final_value_after_tax if bench else np.nan,
            "excess_vs_benchmark": final - bench.final_value_after_tax if bench else np.nan,
            "cagr": ann["cagr"], "vol": ann["vol"], "sharpe": ann["sharpe"],
            "max_drawdown": max_drawdown(values),
            "benchmark_max_drawdown": bench.max_drawdown if bench else np.nan,
            "benchmark_cagr": annualized(bench.history["total_value"])["cagr"] if bench else np.nan,
            "tax_paid": self.tax.total_paid,
            "dividends_after_tax": self.dividends_after_tax,
            "commission": self.commission_paid,
            "stock_trades": int(len(stock_trades)),
            "etf_trades": int(len(trades) - len(stock_trades)),
            "closed_positions": int(len(closed)),
            "win_rate": float((closed["pnl"] > 0).mean()) if len(closed) else np.nan,
            "avg_holding_days": float(closed["holding_days"].mean()) if len(closed) else np.nan,
            "avg_stock_exposure": float((history["stock_value"] / history["total_value"]).mean()),
            "turnover_per_year": (float(stock_trades["amount"].sum()) / float(values.mean()) / years
                                  if len(stock_trades) and years > 0 else 0.0),
            "skipped": len(self.skipped),
            "years": years,
        }
        return {"metrics": metrics, "history": history, "trades": trades, "closed": closed,
                "benchmark": bench, "tax_ledger": self.tax.ledger(), "skipped": pd.DataFrame(self.skipped),
                "config": asdict(self.config)}
