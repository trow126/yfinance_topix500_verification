#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略
毎月、その月に権利確定がある銘柄をランキングし、上位を優待がもらえる単元で買う

銘柄の選び方は2通り:
- objective: 選定時点のデータ（過去1年の配当実績・売買代金・株価）で客観的にランキング
- minkabu: みんかぶ「月別株主優待人気ランキング」の、選定日より前に保存された最新版
  （Wayback Machine から scripts/data/fetch_minkabu_rankings.py で取得）
"""

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yaml

from ..data.edinet_benefits import record_date_in_month
from ..utils.calendar import DividendDateCalculator


@dataclass
class SelectionConfig:
    """銘柄選定の設定"""
    source: str = "objective"            # "objective"（客観指標） / "minkabu"（みんかぶ月別人気ランキング）
    top_n: int = 3                       # 毎月買う銘柄数
    pick: str = "top"                    # minkabu: 条件を満たす銘柄から top（上位）/ bottom（下位）/ random を選ぶ
    rank_by: str = "ranking"             # minkabu: 並べ替え ranking（人気順） / dividend_yield（実績配当利回り順）
    ranking_min_turnover: float = 0      # minkabu: 直近の平均売買代金の下限（円/日）。0 = 条件なし
    ranking_min_yield: float = 0.0       # minkabu: 過去1年の実績配当利回りの下限。0 = 条件なし
    random_seed: int = 0                 # pick: random のときの乱数シード
    max_unit_cost: float = 500_000       # 1単元の購入額の上限（円）
    monthly_budget: float = 0            # 1か月の初回購入額の上限（円）。順に見て収まる銘柄だけ買う。0 = 上限なし
    # --- objective ---
    min_turnover: float = 1_000_000_000  # 直近の平均売買代金の下限（円/日）。人気の代用
    turnover_window: int = 60            # 売買代金の平均をとる営業日数
    min_yield: float = 0.0               # 実績配当利回りの下限
    # --- minkabu ---
    ranking_file: str = "./data/rankings/minkabu_popular_monthly.tsv"
    ranking_max_age_days: int = 400      # これより古いランキングしかない月は買わない
    exclude_keywords: List[str] = field(default_factory=list)    # 優待内容にこの語を含む銘柄は除外
    exclude_categories: List[str] = field(default_factory=list)  # このカテゴリを含む銘柄は除外
    benefits_file: str = ""              # EDINETの株式事務の概要（空なら使わない）
    exclude_continuous_holding: bool = False  # 継続保有が条件の優待を除外するか


@dataclass
class TradingConfig:
    """売買ルールの設定"""
    unit_shares: int = 100               # 最初に買う株数（優待・配当がもらえる単元）
    entry_days_before_ex: int = 2        # 権利落ち日の何営業日前に買うか（2 = 権利付き最終日の前日、0 = 権利落ち日、-5 = 5営業日後）
    exit_target: str = "average_cost"    # 売る価格: average_cost（平均取得単価） / pre_ex_close（権利落ち前日の終値＝窓埋め）
    nanpin_step: float = 0.10            # 初回購入価格から何%下がるごとにナンピンするか
    nanpin_max: int = 2                  # ナンピンの最大回数（初回と同じ株数を買い増す）
    max_holding_days: int = 0            # 権利落ち後、購入からこの暦日数を過ぎたら成行で売る（0 = 期限なし）
    stop_loss_pct: float = 0.0           # ナンピンを使い切った後、平均取得単価からこれだけ下がったら売る（0 = なし）


@dataclass
class CostConfig:
    """取引コストの設定"""
    slippage: float = 0.002
    commission: float = 0.00055
    min_commission: float = 550
    max_commission: float = 1100
    tax_rate: float = 0.20315


@dataclass
class MonthlyRightsConfig:
    """月次権利取り戦略の設定"""
    start_date: str = "2019-01-01"
    end_date: str = "2025-12-31"
    initial_capital: float = 10_000_000
    data_dir: str = "./data/cache/universe"
    results_dir: str = "./data/results/monthly_rights"
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    costs: CostConfig = field(default_factory=CostConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "MonthlyRightsConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(
            **{k: v for k, v in raw.items() if k not in ("selection", "trading", "costs")},
            selection=SelectionConfig(**raw.get("selection", {})),
            trading=TradingConfig(**raw.get("trading", {})),
            costs=CostConfig(**raw.get("costs", {})),
        )


def load_universe(data_dir: str) -> Dict[str, pd.DataFrame]:
    """fetch_universe_data.py で保存した銘柄ごとのデータを読み込む"""
    data = {}
    for path in sorted(Path(data_dir).glob("*.pkl")):
        df = pd.read_pickle(path)
        if not df.empty:
            data[path.stem] = df
    return data


class MarketPanel:
    """全銘柄のデータを日付×銘柄の表にまとめたもの"""

    # 前日終値に対する1回の配当がこれを超えるものはyfinanceのデータ異常とみなして除外する
    # （例: 8303 で1株2億円の配当が記録されている）
    MAX_DIVIDEND_RATIO = 0.2

    def __init__(self, data: Dict[str, pd.DataFrame], turnover_window: int = 60):
        self.close = pd.DataFrame({c: df["Close"] for c, df in data.items()}).sort_index()
        volume = pd.DataFrame({c: df["Volume"] for c, df in data.items()}).reindex(self.close.index)
        self.close_ffill = self.close.ffill()
        self.calendar = self.close.index

        # 選定日より前のデータだけを使うため1日ずらす
        self.avg_turnover = (self.close * volume).rolling(turnover_window, min_periods=turnover_window // 2).mean().shift(1)

        # 株式分割の補正係数（yfinanceの価格は後の分割で遡及調整されるため、
        # 当時の100株 = 調整後の 100 × 係数 株になる）
        splits = pd.DataFrame({c: df["Stock Splits"] for c, df in data.items()}).reindex(self.close.index)
        ratio = splits.where(splits > 0, 1.0).fillna(1.0)
        later = ratio.iloc[::-1].cumprod().iloc[::-1]  # その日以降の分割の累積
        self.split_factor = later.shift(-1).fillna(1.0)  # 当日より後の分割のみ

        self.events = self._build_dividend_events(data)

    def _build_dividend_events(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """権利落ち日・権利確定日・配当額の一覧"""
        rows = []
        self.rejected_dividends = []
        position = {d: i for i, d in enumerate(self.calendar)}
        for code, df in data.items():
            prev_close = df["Close"].shift(1)
            for ex_date, amount in df.loc[df["Dividends"] > 0, "Dividends"].items():
                i = position.get(ex_date)
                if i is None:
                    continue
                ref = prev_close.get(ex_date)
                if pd.isna(ref) or amount / ref > self.MAX_DIVIDEND_RATIO:
                    self.rejected_dividends.append((code, ex_date, float(amount), ref))
                    continue
                # 権利確定日: T+2決済移行後は権利落ち日の1営業日後、それ以前は2営業日後
                offset = 1 if ex_date >= DividendDateCalculator.T2_SETTLEMENT_START else 2
                record = self.calendar[min(i + offset, len(self.calendar) - 1)]
                rows.append((code, ex_date, record, float(amount), i))
        events = pd.DataFrame(rows, columns=["code", "ex_date", "record_date", "dividend", "ex_idx"])
        events["record_month"] = events["record_date"].dt.to_period("M")
        return events.sort_values(["ex_date", "code"]).reset_index(drop=True)

    def price(self, code: str, date: pd.Timestamp) -> Optional[float]:
        """当日の終値（売買のない日はNone）"""
        value = self.close.at[date, code] if code in self.close.columns else None
        return None if value is None or pd.isna(value) else float(value)

    def valuation_prices(self, date: pd.Timestamp) -> Dict[str, float]:
        """時価評価用の価格（売買のない銘柄は直近の終値）"""
        row = self.close_ffill.loc[date]
        return row.dropna().to_dict()


class MonthlyRightsSelector:
    """毎月の購入銘柄を選ぶ"""

    def __init__(self, panel: MarketPanel, config: SelectionConfig, trading: TradingConfig):
        self.panel = panel
        self.config = config
        self.trading = trading

    def select(self, selection_date: pd.Timestamp) -> pd.DataFrame:
        """
        selection_date の月に権利確定がある銘柄から上位を選ぶ

        使う情報は selection_date より前に確定していたものだけ:
        - 権利落ち日の予定（決算期で決まっているため事前に分かる）
        - 過去1年の配当実績、前日までの平均売買代金、前日終値
        """
        panel = self.panel
        month = selection_date.to_period("M")
        sel_idx = panel.calendar.get_loc(selection_date)

        upcoming = panel.events[panel.events["record_month"] == month].copy()
        upcoming["entry_idx"] = upcoming["ex_idx"] - self.trading.entry_days_before_ex
        upcoming = upcoming[(upcoming["entry_idx"] >= sel_idx) & (upcoming["entry_idx"] < len(panel.calendar))]
        upcoming = upcoming.sort_values("ex_date").drop_duplicates("code")
        if upcoming.empty or sel_idx == 0:
            return upcoming.iloc[0:0]

        prev_date = panel.calendar[sel_idx - 1]
        past = panel.events[(panel.events["ex_date"] < selection_date)
                            & (panel.events["ex_date"] >= selection_date - pd.Timedelta(days=365))]
        trailing_dividend = past.groupby("code")["dividend"].sum()

        codes = upcoming["code"]
        last_close = panel.close_ffill.loc[prev_date, codes].to_numpy()
        upcoming["last_close"] = last_close
        upcoming["avg_turnover"] = panel.avg_turnover.loc[prev_date, codes].to_numpy()
        upcoming["unit_cost"] = (last_close * self.trading.unit_shares
                                 * panel.split_factor.loc[prev_date, codes].to_numpy())
        upcoming["trailing_yield"] = trailing_dividend.reindex(codes).fillna(0).to_numpy() / last_close

        c = self.config
        candidates = upcoming[
            (upcoming["avg_turnover"] >= c.min_turnover)
            & (upcoming["unit_cost"] <= c.max_unit_cost)
            & (upcoming["trailing_yield"] > c.min_yield)
        ]
        ranked = candidates.sort_values("trailing_yield", ascending=False)
        # 比較用: 条件を満たす銘柄から下位・ランダムを選ぶこともできる
        if c.pick == "bottom":
            ranked = ranked.tail(c.top_n)
        elif c.pick == "random":
            seed = int.from_bytes(f"{c.random_seed}-{selection_date:%Y%m}".encode(), "little") % (2**32)
            ranked = ranked.sample(min(c.top_n, len(ranked)), random_state=seed)
        else:
            ranked = ranked.head(c.top_n)
        ranked = ranked.assign(entry_date=panel.calendar[ranked["entry_idx"].to_numpy()],
                               selection_date=selection_date, unit_shares=self.trading.unit_shares)
        return ranked.reset_index(drop=True)


def load_rankings(path: str) -> pd.DataFrame:
    """fetch_minkabu_rankings.py で保存したランキングを読み込む"""
    rankings = pd.read_csv(path, sep="\t", dtype={"code": str}, parse_dates=["snapshot"])
    rankings["yutai_content"] = rankings["yutai_content"].fillna("")
    rankings["categories"] = rankings["categories"].fillna("")
    if "yutai_months" not in rankings:
        rankings["yutai_months"] = ""
    rankings["yutai_months"] = rankings["yutai_months"].fillna("").astype(str)
    return rankings


def yutai_value_per_record(yutai_yield, min_invest_yen, yutai_months: str) -> float:
    """
    1回の権利確定で受け取る優待の価値（円）の見積もり
    みんかぶの優待利回りは「年間の優待価値 ÷ 最低投資金額」なので、年の権利確定回数で割る
    """
    if pd.isna(yutai_yield) or pd.isna(min_invest_yen):
        return 0.0
    times = len([m for m in str(yutai_months).split("|") if m]) or 1
    return float(yutai_yield) / 100 * float(min_invest_yen) / times


class RankingSelector:
    """
    みんかぶ月別優待人気ランキングから毎月の購入銘柄を選ぶ

    - 選定日より前に保存された、その月のランキングのうち最新のものを使う
    - 除外キーワード・カテゴリに該当する優待、株価データがない銘柄、予算超過は飛ばして上位N銘柄
    - 株数はランキングの「優待発生株数」。古い形式で載っていない場合は最低投資金額÷当時の株価で推定
    - 優待の権利確定日は次の順で決める
      1. 選定日より前に提出された最新の有価証券報告書（EDINET）の「株主に対する特典」の基準日
      2. 同じ月の配当の権利落ち日
      3. 月末（どちらも分からない場合の仮定）
    """

    # これより古い有報の優待情報は使わない（有報は年1回なので約1年半）
    MAX_REPORT_AGE_DAYS = 550

    def __init__(self, panel: MarketPanel, config: SelectionConfig, trading: TradingConfig,
                 rankings: pd.DataFrame, benefits: Optional[pd.DataFrame] = None):
        self.panel = panel
        self.config = config
        self.trading = trading
        self.rankings = rankings
        self.benefits = {code: g for code, g in benefits.groupby("code")} if benefits is not None else {}
        self.excluded: List[dict] = []

    def _latest_benefit(self, code: str, selection_date: pd.Timestamp):
        """選定日より前に提出された最新の有報の優待情報"""
        reports = self.benefits.get(code)
        if reports is None:
            return None
        oldest = selection_date - pd.Timedelta(days=self.MAX_REPORT_AGE_DAYS)
        usable = reports[(reports["submitted"] < selection_date) & (reports["submitted"] >= oldest)]
        return None if usable.empty else usable.iloc[-1]["benefit"]

    def _is_excluded(self, row) -> Optional[str]:
        for word in self.config.exclude_keywords:
            if word in row.yutai_content:
                return f"優待内容に「{word}」"
        categories = set(row.categories.split("|"))
        for category in self.config.exclude_categories:
            if category in categories:
                return f"カテゴリ「{category}」"
        return None

    def _real_price(self, code: str, date: pd.Timestamp) -> Optional[float]:
        """その日の実際の株価（分割の遡及調整を戻したもの）"""
        idx = self.panel.calendar.searchsorted(date, side="right") - 1
        if idx < 0:
            return None
        day = self.panel.calendar[idx]
        price = self.panel.close_ffill.at[day, code]
        return None if pd.isna(price) else float(price * self.panel.split_factor.at[day, code])

    def _ex_idx_for_record(self, record: pd.Timestamp) -> Optional[int]:
        """権利確定日（暦日）から権利落ち日のindexを求める。休日なら直前の営業日で判定"""
        idx = self.panel.calendar.searchsorted(record, side="right") - 1
        if idx < 0:
            return None
        offset = 1 if record >= DividendDateCalculator.T2_FIRST_RECORD_DATE else 2
        return idx - offset

    def _rights_dates(self, code: str, month: pd.Period, sel_idx: int, benefit=None):
        """(権利落ち日のindex, 権利確定日, 配当額, 決め方 edinet/dividend/assumed)"""
        panel = self.panel
        events = panel.events[(panel.events["code"] == code) & (panel.events["record_month"] == month)]
        events = events[events["ex_idx"] - self.trading.entry_days_before_ex >= sel_idx]
        dividend = float(events.iloc[0]["dividend"]) if not events.empty else 0.0

        if benefit is not None and benefit.has_benefit:
            record = record_date_in_month(benefit, month)
            if record is not None:
                ex_idx = self._ex_idx_for_record(record)
                if ex_idx is not None:
                    return ex_idx, record, dividend, "edinet"
        if not events.empty:
            e = events.iloc[0]
            return int(e["ex_idx"]), e["record_date"], dividend, "dividend"
        # どちらも分からない月は、月末（最終営業日）を権利確定日とみなす
        in_month = panel.calendar[panel.calendar.to_period("M") == month]
        if len(in_month) == 0:
            return None
        record = in_month[-1]
        return self._ex_idx_for_record(record), record, 0.0, "assumed"

    def select(self, selection_date: pd.Timestamp) -> pd.DataFrame:
        panel = self.panel
        month = selection_date.to_period("M")
        sel_idx = panel.calendar.get_loc(selection_date)
        oldest = selection_date - pd.Timedelta(days=self.config.ranking_max_age_days)

        r = self.rankings
        available = r[(r["month"] == selection_date.month) & (r["snapshot"] < selection_date)
                      & (r["snapshot"] >= oldest)]
        if available.empty or sel_idx == 0:
            return pd.DataFrame()
        snapshot = available["snapshot"].max()
        ranking = available[available["snapshot"] == snapshot].sort_values("rank")

        prev_date = panel.calendar[sel_idx - 1]
        past = panel.events[(panel.events["ex_date"] < selection_date)
                            & (panel.events["ex_date"] >= selection_date - pd.Timedelta(days=365))]
        trailing_dividend = past.groupby("code")["dividend"].sum()
        c = self.config
        picks = []
        for row in ranking.itertuples():
            reason = self._is_excluded(row)
            if reason is None and row.code not in panel.close.columns:
                reason = "株価データなし"
            if reason is None:
                # 客観指標（選定日の前日までのデータ）。価格・配当はどちらも分割調整後なので比率はそのまま使える
                turnover = panel.avg_turnover.at[prev_date, row.code]
                close = panel.close_ffill.at[prev_date, row.code]
                trailing_yield = trailing_dividend.get(row.code, 0.0) / close if close > 0 else 0.0
                if c.ranking_min_turnover and not (turnover >= c.ranking_min_turnover):
                    reason = "売買代金が少ない"
                elif c.ranking_min_yield and trailing_yield < c.ranking_min_yield:
                    reason = "配当利回りが低い"
            benefit = self._latest_benefit(row.code, selection_date) if reason is None else None
            if (reason is None and benefit is not None and benefit.continuous_holding == "required"
                    and self.config.exclude_continuous_holding):
                reason = "継続保有が条件の優待"
            if reason is None:
                dates = self._rights_dates(row.code, month, sel_idx, benefit)
                if dates is None or dates[0] is None or dates[0] - self.trading.entry_days_before_ex < sel_idx:
                    reason = "権利日が選定日より前"
                elif dates[0] - self.trading.entry_days_before_ex >= len(panel.calendar):
                    reason = "購入日がデータの期間外"
            if reason is None:
                if pd.notna(row.yutai_shares):
                    shares = int(row.yutai_shares)
                else:
                    then = self._real_price(row.code, snapshot)
                    shares = 100
                    if then and pd.notna(row.min_invest_yen):
                        shares = max(100, int(round(row.min_invest_yen / then / 100)) * 100)
                now = self._real_price(row.code, prev_date)
                if now is None:
                    reason = "株価データなし"
                elif now * shares > self.config.max_unit_cost:
                    reason = f"予算超過（{now * shares:,.0f}円）"
            if reason is not None:
                self.excluded.append({"selection_date": selection_date, "snapshot": snapshot,
                                      "rank": row.rank, "code": row.code, "name": row.name,
                                      "yutai_content": row.yutai_content, "reason": reason})
                continue

            ex_idx, record_date, dividend, source = dates
            # 継続保有が条件の優待は、初回の購入ではもらえないものとして0円にする
            continuous = benefit is not None and benefit.continuous_holding == "required"
            yutai_value = 0.0 if continuous else yutai_value_per_record(
                row.yutai_yield, row.min_invest_yen, row.yutai_months)
            picks.append({
                "yutai_yield": row.yutai_yield, "yutai_months": row.yutai_months,
                "yutai_value": yutai_value,
                "code": row.code, "name": row.name, "rank": row.rank, "snapshot": snapshot,
                "yutai_content": row.yutai_content, "categories": row.categories,
                "ex_date": panel.calendar[ex_idx], "record_date": record_date, "dividend": dividend,
                "rights_date_source": source, "rights_date_assumed": source == "assumed",
                "edinet_benefit": None if benefit is None else benefit.has_benefit,
                "continuous_holding": None if benefit is None else benefit.continuous_holding,
                "unit_shares": shares, "unit_cost": now * shares,
                "avg_turnover": turnover, "trailing_yield": trailing_yield,
                "entry_date": panel.calendar[ex_idx - self.trading.entry_days_before_ex],
                "selection_date": selection_date,
            })

        if c.rank_by == "dividend_yield":
            picks.sort(key=lambda p: -p["trailing_yield"])
        # 比較用: 条件を満たす銘柄のうち下位やランダムを選ぶこともできる
        n = self.config.top_n
        if self.config.pick == "bottom":
            picks = picks[::-1]
        elif self.config.pick == "random":
            rng = random.Random(f"{self.config.random_seed}-{selection_date:%Y%m}")
            picks = rng.sample(picks, len(picks))
        return pd.DataFrame(self._within_budget(picks, n))

    def _within_budget(self, picks: List[dict], n: int) -> List[dict]:
        """並び順に見て、銘柄数と月の予算に収まるものを選ぶ（予算を超える銘柄は飛ばす）"""
        budget = self.config.monthly_budget
        chosen, total = [], 0.0
        for p in picks:
            if len(chosen) >= n:
                break
            if budget and total + p["unit_cost"] > budget:
                continue
            chosen.append(p)
            total += p["unit_cost"]
        return chosen
