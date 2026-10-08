#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略のバックテストエンジン

1. 毎月の最初の営業日に、その月に権利確定がある銘柄から上位N銘柄を選ぶ
2. 権利落ち日の数営業日前に単元株を買う（保有中の銘柄は買わない）
3. 初回購入価格から一定割合下がるごとに、初回と同じ株数をナンピンする
4. 権利落ち日以降、終値が平均取得単価以上になったら全株売る（期限なし）
5. 保有中に権利落ち日を迎えた銘柄は、前日時点の株数で配当を受け取る（税引後）
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..utils.logger import log
from ..strategy.monthly_rights import (
    MarketPanel, MonthlyRightsConfig, MonthlyRightsSelector, RankingSelector, load_rankings,
)
from ..data.edinet_benefits import load_benefits
from .portfolio import Portfolio


@dataclass
class CycleState:
    """保有中の銘柄ごとの状態"""
    code: str
    first_price: float
    unit_shares: int          # 初回株数（分割補正後）
    ex_date: pd.Timestamp     # 狙っている権利落ち日
    entry_date: pd.Timestamp
    nanpin_count: int = 0
    yutai_value: float = 0.0  # 狙っている権利確定で受け取る優待の価値（見積もり）
    target_price: Optional[float] = None  # 売る価格（窓埋めの場合は権利落ち前日の終値）。Noneなら平均取得単価


class MonthlyRightsEngine:
    """月次権利取り戦略のバックテスト"""

    def __init__(self, config: MonthlyRightsConfig, data: Dict[str, pd.DataFrame],
                 panel: Optional[MarketPanel] = None):
        self.config = config
        # 条件を変えて何度も回すときは panel を使い回す（作成に数秒かかる）
        self.panel = panel or MarketPanel(data, config.selection.turnover_window)
        if config.selection.source == "minkabu":
            rankings = load_rankings(config.selection.ranking_file)
            benefits = load_benefits(config.selection.benefits_file) if config.selection.benefits_file else None
            self.selector = RankingSelector(self.panel, config.selection, config.trading, rankings, benefits)
        else:
            self.selector = MonthlyRightsSelector(self.panel, config.selection, config.trading)
        self.portfolio = Portfolio(config.initial_capital)

        start, end = pd.Timestamp(config.start_date), pd.Timestamp(config.end_date)
        calendar = self.panel.calendar
        self.trading_days = calendar[(calendar >= start) & (calendar <= end)]

        self.states: Dict[str, CycleState] = {}
        self.pending_entries: Dict[pd.Timestamp, List[dict]] = {}
        self.selections: List[pd.DataFrame] = []
        self.skipped: List[dict] = []
        self.nanpin_trades = 0
        self.yutai_received: List[dict] = []

        dividends = self.panel.events.set_index(["ex_date", "code"])["dividend"]
        self.dividends_by_date = {d: g.droplevel(0).to_dict() for d, g in dividends.groupby(level=0)}

    # ------------------------------------------------------------------
    def run(self) -> Dict:
        current_month = None
        for date in self.trading_days:
            if date.to_period("M") != current_month:
                current_month = date.to_period("M")
                self._select(date)
            self._process_day(date)
        return self._results()

    def _select(self, date: pd.Timestamp) -> None:
        picks = self.selector.select(date)
        if picks.empty:
            return
        self.selections.append(picks)
        for row in picks.to_dict("records"):
            self.pending_entries.setdefault(row["entry_date"], []).append(row)

    def _process_day(self, date: pd.Timestamp) -> None:
        # 1. 配当（権利は前日の保有株に付くので、当日の売買より先に計上）
        for code, dividend in self.dividends_by_date.get(date, {}).items():
            if self.portfolio.position_manager.get_position(code):
                self.portfolio.update_dividend(code, dividend * (1 - self.config.costs.tax_rate), date)
        # 優待（現金ではないので口座には入れず、見積もり額を別に記録する）
        for code, state in self.states.items():
            if state.ex_date == date:
                self.yutai_received.append({"date": date, "code": code, "value": state.yutai_value})

        # 2. 保有銘柄の売却・ナンピン
        for code in list(self.states):
            price = self.panel.price(code, date)
            if price is None:
                continue
            state = self.states[code]
            position = self.portfolio.position_manager.get_position(code)
            t = self.config.trading
            after_rights = date >= state.ex_date
            if after_rights and price >= (state.target_price or position.average_price):
                self._sell(code, date, price,
                           "Window filled" if state.target_price else "Recovered to average cost")
            elif after_rights and t.max_holding_days and (date - state.entry_date).days >= t.max_holding_days:
                self._sell(code, date, price, "Max holding period")
            elif (t.stop_loss_pct and state.nanpin_count >= t.nanpin_max
                  and price <= position.average_price * (1 - t.stop_loss_pct)):
                self._sell(code, date, price, "Stop loss after nanpin")
            elif self._nanpin_due(state, price):
                if self._buy(code, date, price, state.unit_shares, "Add (nanpin)"):
                    state.nanpin_count += 1
                    self.nanpin_trades += 1

        # 3. 新規購入
        for row in self.pending_entries.pop(date, []):
            code = row["code"]
            if code in self.states:
                continue  # 前回分を保有中
            price = self.panel.price(code, date)
            if price is None:
                continue
            # unit_shares は当時の実株数。yfinanceの価格は後の分割で遡及調整されているので補正する
            shares = int(round(row["unit_shares"] * self.panel.split_factor.at[date, code]))
            if self._buy(code, date, price, shares, "Entry (monthly rights)", row):
                self.states[code] = CycleState(code, price, shares, row["ex_date"], date,
                                               yutai_value=float(row.get("yutai_value", 0.0) or 0.0),
                                               target_price=self._target_price(code, row["ex_date"]))

        # 4. 時価評価
        self.portfolio.mark_to_market(date, self.panel.valuation_prices(date))

    def _target_price(self, code: str, ex_date: pd.Timestamp) -> Optional[float]:
        """窓埋めで売る場合の目標価格（権利落ち前日の終値）"""
        if self.config.trading.exit_target != "pre_ex_close":
            return None
        idx = self.panel.calendar.get_loc(ex_date) - 1
        price = self.panel.close_ffill.iat[idx, self.panel.close_ffill.columns.get_loc(code)]
        return None if pd.isna(price) else float(price)

    def _nanpin_due(self, state: CycleState, price: float) -> bool:
        t = self.config.trading
        if state.nanpin_count >= t.nanpin_max:
            return False
        return price <= state.first_price * (1 - t.nanpin_step * (state.nanpin_count + 1))

    def _commission(self, amount: float) -> float:
        c = self.config.costs
        return min(max(amount * c.commission, c.min_commission), c.max_commission)

    def _buy(self, code: str, date, price: float, shares: int, reason: str,
             row: Optional[dict] = None) -> bool:
        fill = price * (1 + self.config.costs.slippage)
        commission = self._commission(fill * shares)
        dividend_info = None
        if row is not None:
            dividend_info = {"ex_dividend_date": row["ex_date"], "record_date": row["record_date"],
                             "dividend_amount": row["dividend"]}
        ok = self.portfolio.execute_buy(code, date.to_pydatetime(), fill, shares, commission,
                                        reason, dividend_info)
        if not ok:
            self.skipped.append({"date": date, "code": code, "reason": reason,
                                 "required": fill * shares + commission, "cash": self.portfolio.cash})
        return ok

    def _sell(self, code: str, date, price: float, reason: str) -> None:
        fill = price * (1 - self.config.costs.slippage)
        position = self.portfolio.position_manager.get_position(code)
        commission = self._commission(fill * position.total_shares)
        self.portfolio.execute_sell(code, date.to_pydatetime(), fill, commission, reason)
        del self.states[code]

    # ------------------------------------------------------------------
    def _results(self) -> Dict:
        history = self.portfolio.get_portfolio_history_df()
        pm = self.portfolio.position_manager
        positions = pm.get_positions_summary()
        last_date = self.trading_days[-1]
        prices = self.panel.valuation_prices(last_date)

        if not positions.empty:
            positions["nanpin_count"] = positions["trade_count"] - 1 - (positions["status"] == "CLOSED")
            open_mask = positions["status"] == "OPEN"
            positions.loc[open_mask, "last_price"] = positions.loc[open_mask, "ticker"].map(prices)
            positions.loc[open_mask, "unrealized_pnl"] = (
                (positions["last_price"] - positions["average_price"]) * positions["total_shares"])
            end = pd.Timestamp(last_date)
            exit_dates = pd.to_datetime(positions["exit_date"]).fillna(end)
            positions["holding_days"] = (exit_dates - pd.to_datetime(positions["entry_date"])).dt.days

        metrics = self._metrics(history, positions)
        selections = pd.concat(self.selections, ignore_index=True) if self.selections else pd.DataFrame()
        return {
            "metrics": metrics,
            "positions": positions,
            "trades": pm.get_trades_dataframe(),
            "portfolio_history": history,
            "selections": selections,
            "skipped": pd.DataFrame(self.skipped),
            "excluded": pd.DataFrame(getattr(self.selector, "excluded", [])),
            "config": asdict(self.config),
        }

    def _metrics(self, history: pd.DataFrame, positions: pd.DataFrame) -> Dict:
        values = history["total_value"]
        daily = values.pct_change().dropna()
        years = (values.index[-1] - values.index[0]).days / 365.25
        final = float(values.iloc[-1])
        initial = self.config.initial_capital
        invested = history["positions_value"]

        closed = positions[positions["status"] == "CLOSED"] if not positions.empty else positions
        opened = positions[positions["status"] == "OPEN"] if not positions.empty else positions
        return {
            "initial_capital": initial,
            "final_value": final,
            "total_return": final / initial - 1,
            "cagr": (final / initial) ** (1 / years) - 1 if years > 0 else 0.0,
            "annualized_volatility": float(daily.std() * np.sqrt(252)),
            "max_drawdown": float((values / values.cummax() - 1).min()),
            "total_dividend_after_tax": self.portfolio.total_dividend,
            "total_commission": self.portfolio.total_commission,
            "cycles": int(len(positions)),
            "closed_cycles": int(len(closed)),
            "open_cycles": int(len(opened)),
            "win_rate_closed": float((closed["realized_pnl"] > 0).mean()) if len(closed) else 0.0,
            "realized_pnl": float(closed["realized_pnl"].sum()) if len(closed) else 0.0,
            "unrealized_pnl_open": float(opened["unrealized_pnl"].sum()) if len(opened) else 0.0,
            "avg_holding_days_closed": float(closed["holding_days"].mean()) if len(closed) else 0.0,
            "median_holding_days_closed": float(closed["holding_days"].median()) if len(closed) else 0.0,
            "max_holding_days": int(positions["holding_days"].max()) if len(positions) else 0,
            "nanpin_trades": self.nanpin_trades,
            "skipped_for_cash": len(self.skipped),
            "avg_invested": float(invested.mean()),
            "max_invested": float(invested.max()),
            # 口座全体ではなく「実際に投資していた額」に対する年率（資金効率の比較用）
            "profit": final - initial,
            "return_on_invested": ((final - initial) / float(invested.mean()) / years
                                   if invested.mean() > 0 and years > 0 else 0.0),
            "worst_open_pnl": float(opened["unrealized_pnl"].min()) if len(opened) else 0.0,
            "exit_reasons": closed["exit_reason"].value_counts().to_dict() if len(closed) else {},
            # 優待（見積もり。現金ではないので上の損益には含まない）
            "yutai_records": len(self.yutai_received),
            "yutai_records_valued": sum(1 for y in self.yutai_received if y["value"] > 0),
            "yutai_value": float(sum(y["value"] for y in self.yutai_received)),
        }


def save_results(results: Dict, results_dir: str) -> Path:
    """結果をCSV/JSONで保存し、出力先ディレクトリを返す"""
    import json
    out = Path(results_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("positions", "trades", "portfolio_history", "selections", "skipped", "excluded"):
        df = results[name]
        if not df.empty:
            df.to_csv(out / f"{name}.csv", index=(name == "portfolio_history"), encoding="utf-8-sig")
    with open(out / "metrics.json", "w", encoding="utf-8") as f:
        json.dump({"metrics": results["metrics"], "config": results["config"]}, f,
                  ensure_ascii=False, indent=2, default=str)
    log.info(f"Results saved to {out}")
    return out
