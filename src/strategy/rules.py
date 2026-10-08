#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
インデックス超えを調べるためのルール型戦略（src/backtest/rules_engine.py で動かす）

どの戦略も「選定日の前日までに分かる情報」だけを使う:
- 価格・売買代金は panel.close_ffill / panel.avg_turnover（avg_turnover は 1 日ずらし済み）
- 配当は権利落ち日が選定日より前のものだけ

候補の絞り方（共通）: 直近 60 営業日の平均売買代金が min_turnover 以上、前日の終値がある、
データ異常銘柄（src/data/quality.py）でない、上場から lookback 日以上たっている。
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import pandas as pd

from ..backtest.rules_engine import Holding, Orders
from .monthly_rights import MarketPanel


# ---------------------------------------------------------------------- 共通
class Candidates:
    """候補銘柄と、その日に使える特徴量（前日までのデータ）"""

    def __init__(self, panel: MarketPanel, min_turnover: float = 1_000_000_000,
                 excluded: Optional[Set[str]] = None, lookback: int = 240):
        # lookback: 上場からこの営業日数たった銘柄だけを候補にする。universe（2018-01-04〜）で
        # 2019 年 1 月の最初のリバランスから候補が出るように 252 ではなく 240 にしている
        self.panel = panel
        self.min_turnover = min_turnover
        self.excluded = set(excluded or ())
        self.lookback = lookback
        close = panel.close_ffill
        self._ret = close.pct_change(fill_method=None)
        # 各銘柄の最初のデータの位置（営業日の番号）。上場から lookback 営業日たっているかの判定に使う
        first_valid = close.apply(lambda s: s.first_valid_index())
        self._first_pos = pd.Series(close.index.get_indexer(first_valid.fillna(close.index[-1])), index=close.columns)
        # 直近 1 年の配当合計（権利落ち日ベース、その日より前のものだけ）
        ev = panel.events
        div = ev.pivot_table(index="ex_date", columns="code", values="dividend", aggfunc="sum")
        div = div.reindex(index=close.index, columns=close.columns).fillna(0.0)  # 無配銘柄は 0
        self._trailing_div = div.rolling(252, min_periods=1).sum().shift(1)
        # その前の 1 年（253〜504 営業日前）の配当合計。データの先頭付近は窓が 200 営業日以上あれば使う
        # （2013-01 開始のデータで 2015-01 の選定から減配判定ができるように。短い分は合計が小さくなり「減配なし」側に倒れる）
        self._prev_div = div.rolling(252, min_periods=200).sum().shift(253)

    def _prev(self, date: pd.Timestamp) -> Optional[pd.Timestamp]:
        i = self.panel.calendar.get_loc(date)
        return None if i == 0 else self.panel.calendar[i - 1]

    def frame(self, date: pd.Timestamp) -> pd.DataFrame:
        """その日の候補と特徴量。列: close, turnover, mom_12_1, vol_252, div_yield, ret_ytd"""
        prev = self._prev(date)
        if prev is None:
            return pd.DataFrame()
        close = self.panel.close_ffill
        i = close.index.get_loc(prev)
        px = close.loc[prev]
        turnover = self.panel.avg_turnover.loc[date]  # すでに 1 日ずらし済み
        listed_ok = self._first_pos <= i - self.lookback
        ok = px.notna() & (turnover >= self.min_turnover) & listed_ok
        ok &= ~px.index.isin(self.excluded)
        codes = px.index[ok.to_numpy()]
        if len(codes) == 0:
            return pd.DataFrame()
        f = pd.DataFrame(index=codes)
        f["close"] = px[codes]
        f["turnover"] = turnover[codes]
        # 1 単元（100 株）の価格。yfinance の価格は後の分割で遡及調整されているので当時の株数に戻す
        f["unit_cost"] = px[codes] * 100 * self.panel.split_factor.loc[prev, codes].fillna(1.0)
        # 12-1 モメンタム: 約 1 年前〜1 か月前の終値の変化率
        p_12 = close.iloc[max(i - 252, 0)][codes]
        p_1 = close.iloc[max(i - 21, 0)][codes]
        f["mom_12_1"] = p_1 / p_12 - 1
        f["mom_6_1"] = p_1 / close.iloc[max(i - 126, 0)][codes] - 1
        r = self._ret.iloc[max(i - 251, 0):i + 1][codes]
        f["vol_252"] = r.std()
        f["div_12"] = self._trailing_div.loc[prev, codes]
        f["div_prev12"] = self._prev_div.loc[prev, codes]
        f["div_yield"] = f["div_12"] / px[codes]
        # 減配なし: 直近 12 か月の配当合計がその前の 12 か月以上で、その前の 12 か月に配当がある
        f["no_cut"] = (f["div_12"] >= f["div_prev12"]) & (f["div_prev12"] > 0)
        year_start = close.index[close.index.year == prev.year][0]
        f["ret_ytd"] = px[codes] / close.loc[year_start, codes] - 1
        return f


def _lot_yen(equity: float, n: int, weight: float) -> float:
    return equity * weight / n


# ---------------------------------------------------------------------- H1 ファクター
@dataclass
class FactorStrategy:
    """
    毎月（または毎四半期）の最初の営業日に、候補をファクターの合成スコアで並べて上位 n 銘柄を等金額で持つ。
    すでに保有していて順位が keep_rank 以内なら持ち続ける（売買を減らす）。
    factors: "mom_12_1", "low_vol"(= -vol_252), "div_yield", "mom_6_1" の組み合わせ。
    pick: "top" / "bottom" / "random"（random は同じ候補から毎月ランダムに n 銘柄。比較用）
          / "random_sticky"（銘柄ごとに年初に引いた乱数を順位にする。毎月引き直さないので売買回数が
          ファクター戦略に近い。比較用。事後に追加: docs/research/hypotheses.md 7 章）
    """
    candidates: Candidates
    name: str = "factor"
    factors: List[str] = field(default_factory=lambda: ["mom_12_1"])
    n: int = 20
    keep_rank: int = 40
    rebalance: str = "M"            # "M" 毎月 / "Q" 3 か月ごと（1・4・7・10 月） / "H" 半年ごと（1・7 月）
    weight: float = 1.0             # 株に充てる口座の割合（残りは 1306）
    pick: str = "top"
    seed: int = 0
    no_cut: bool = False            # True なら「直近 12 か月の配当合計 ≥ その前 12 か月 > 0」の銘柄だけを候補にする（減配回避）
    _last_period: Optional[pd.Period] = None

    def _is_rebalance_day(self, date: pd.Timestamp) -> bool:
        period = date.to_period("M")
        if period == self._last_period:
            return False
        if self.rebalance == "Q" and date.month % 3 != 1:
            return False
        if self.rebalance == "H" and date.month not in (1, 7):
            return False
        self._last_period = period
        return True

    def score(self, f: pd.DataFrame) -> pd.Series:
        cols = []
        for name in self.factors:
            if name == "low_vol":
                cols.append((-f["vol_252"]).rank(pct=True))
            else:
                cols.append(f[name].rank(pct=True))
        return pd.concat(cols, axis=1).mean(axis=1)

    def orders(self, date, panel, holdings: Dict[str, Holding], equity: float) -> Optional[Orders]:
        if not self._is_rebalance_day(date):
            return None
        f = self.candidates.frame(date)
        if f.empty:
            return None
        yen = _lot_yen(equity, self.n, self.weight)
        # 1 単元が 1 銘柄の予算を超える銘柄は買えないので候補から外す
        f = f.dropna(subset=["mom_12_1", "vol_252"])
        f = f[f["unit_cost"] <= yen]
        if self.no_cut:
            f = f[f["no_cut"].fillna(False)]
        if f.empty:
            return None
        if self.pick == "random":
            rng = random.Random(f"{self.seed}-{date:%Y%m}")
            chosen = rng.sample(list(f.index), min(self.n, len(f)))
            rank = pd.Series(range(1, len(chosen) + 1), index=chosen)
        elif self.pick == "random_sticky":
            scores = pd.Series({c: random.Random(f"{self.seed}-{date:%Y}-{c}").random() for c in f.index})
            s = scores.sort_values()
            rank = pd.Series(range(1, len(s) + 1), index=s.index)
            chosen = list(s.index[:self.n])
        else:
            s = self.score(f).sort_values(ascending=(self.pick == "bottom"))
            rank = pd.Series(range(1, len(s) + 1), index=s.index)
            chosen = list(s.index[:self.n])
        keep = [c for c in holdings if c in rank.index and rank[c] <= self.keep_rank]
        sells = [c for c in holdings if c not in keep]
        slots = self.n - len(keep)
        new = [c for c in chosen if c not in keep][:max(slots, 0)]
        return Orders(sells=sells, buys={c: yen for c in new}, reason=f"{self.name} rebalance",
                      meta={c: {"rank": int(rank.get(c, 0))} for c in new})


# ---------------------------------------------------------------------- H5 権利落ち後の戻り
@dataclass
class PostExRebound:
    """
    権利落ち日の終値で、その日に権利落ちした候補のうち実績配当利回りの高い順に n_per_day 銘柄を買い、
    終値が権利落ち前日の終値以上（窓埋め）になったら売る。max_days 暦日を過ぎたら売る。
    同時に持てる銘柄は max_positions まで。1 銘柄の金額は equity * weight / max_positions。
    pick: "top"（利回り順）/ "random"（同じ候補からランダム）
    """
    candidates: Candidates
    name: str = "post_ex"
    n_per_day: int = 3
    max_positions: int = 15
    max_days: int = 90
    min_yield: float = 0.0
    weight: float = 1.0
    pick: str = "top"
    seed: int = 0
    entry_offset: int = 0           # 権利落ち日の何営業日後に買うか（0 = 当日）

    def __post_init__(self):
        ev = self.candidates.panel.events
        self._by_ex_idx = {int(i): g for i, g in ev.groupby("ex_idx")}

    def orders(self, date, panel, holdings, equity) -> Optional[Orders]:
        sells, buys, meta = [], {}, {}
        # 出口
        for code, h in holdings.items():
            target = h.meta.get("pre_ex_close")
            price = panel.price(code, date)
            if price is not None and target and price >= target:
                sells.append(code)
            elif (date - h.entry_date).days >= self.max_days:
                sells.append(code)
        # 入口
        idx = panel.calendar.get_loc(date) - self.entry_offset
        todays = self._by_ex_idx.get(int(idx))
        if todays is not None and idx >= 1:
            f = self.candidates.frame(date)
            if not f.empty:
                pre_ex = panel.close_ffill.iloc[idx - 1]
                yen = _lot_yen(equity, self.max_positions, self.weight)
                f = f[f["unit_cost"] <= yen]
                # その権利落ちの配当額（予想配当として事前に分かるものとみなす）÷ 権利落ち前日の終値
                ev = todays.drop_duplicates("code").set_index("code")["dividend"]
                codes = [c for c in ev.index if c in f.index and c not in holdings and pd.notna(pre_ex[c])]
                ev_yield = pd.Series({c: float(ev[c]) / float(pre_ex[c]) for c in codes})
                ev_yield = ev_yield[ev_yield > self.min_yield]
                if self.pick == "random":
                    rng = random.Random(f"{self.seed}-{date:%Y%m%d}")
                    order = rng.sample(list(ev_yield.index), len(ev_yield))
                else:
                    order = list(ev_yield.sort_values(ascending=False).index)
                open_slots = self.max_positions - (len(holdings) - len(sells))
                for c in order[:max(min(self.n_per_day, open_slots), 0)]:
                    buys[c] = yen
                    meta[c] = {"pre_ex_close": float(pre_ex[c]), "ex_yield": float(ev_yield[c])}
        if not sells and not buys:
            return None
        return Orders(sells=sells, buys=buys, reason=self.name, meta=meta)


# ---------------------------------------------------------------------- H6 季節性
@dataclass
class YearEndLosers:
    """
    年末の節税売りの反動を狙う: 12 月の最終営業日の entry_days_before 営業日前に、
    年初来リターンが低い順に n 銘柄を買い、翌年 1 月の最終営業日（exit_month_end=1）に売る。
    それ以外の期間は 1306 のまま（待機資金）。
    """
    candidates: Candidates
    name: str = "year_end_losers"
    n: int = 20
    entry_days_before: int = 3
    exit_month: int = 1
    weight: float = 1.0
    pick: str = "bottom"            # "bottom" 年初来下位 / "top" 上位 / "random"
    seed: int = 0

    def orders(self, date, panel, holdings, equity) -> Optional[Orders]:
        cal = panel.calendar
        i = cal.get_loc(date)
        # 出口: exit_month の最終営業日
        if holdings and date.month == self.exit_month and (i + 1 >= len(cal) or cal[i + 1].month != self.exit_month):
            return Orders(sells=list(holdings), reason=f"{self.name} exit")
        # 入口: 12 月の最終営業日の entry_days_before 営業日前
        if date.month == 12:
            j = i + self.entry_days_before
            if j < len(cal) and cal[j].month == 12 and (j + 1 >= len(cal) or cal[j + 1].month != 12):
                f = self.candidates.frame(date)
                if f.empty:
                    return None
                yen = _lot_yen(equity, self.n, self.weight)
                f = f.dropna(subset=["ret_ytd"])
                f = f[f["unit_cost"] <= yen]
                if f.empty:
                    return None
                if self.pick == "random":
                    rng = random.Random(f"{self.seed}-{date:%Y}")
                    chosen = rng.sample(list(f.index), min(self.n, len(f)))
                else:
                    chosen = list(f.sort_values("ret_ytd", ascending=(self.pick == "bottom")).index[:self.n])
                return Orders(buys={c: yen for c in chosen if c not in holdings}, reason=f"{self.name} entry",
                              meta={c: {"ret_ytd": float(f.at[c, "ret_ytd"])} for c in chosen})
        return None


@dataclass
class EventHold:
    """
    イベント（例: 大量保有報告書の提出）の翌営業日の終値で買い、hold_days 営業日後の終値で売る。

    events: 列 date（イベント日。提出日）と code。同じ日に同じ銘柄が複数あっても 1 回だけ買う。
    候補条件は Candidates（売買代金・上場日数・異常値除外）に加え、1 単元 ≤ 1 銘柄の予算。
    同時保有は max_positions まで、1 銘柄の金額は口座評価額 × weight ÷ max_positions。余りは 1306。
    pick: "event"（イベント銘柄そのもの） / "random"（同じ日に同じ候補からランダムに同じ数だけ選ぶ。比較用）
    """
    candidates: Candidates
    events: pd.DataFrame
    name: str = "event_hold"
    hold_days: int = 60
    max_positions: int = 10
    entry_lag: int = 1              # イベント日の何営業日後の終値で買うか
    weight: float = 1.0
    pick: str = "event"
    seed: int = 0

    def __post_init__(self):
        cal = self.candidates.panel.calendar
        ev = self.events.copy()
        ev["date"] = pd.to_datetime(ev["date"])
        # イベント日より後の最初の営業日 + (entry_lag - 1)
        pos = cal.searchsorted(ev["date"].to_numpy(), side="right") + (self.entry_lag - 1)
        ev["entry_idx"] = pos
        ev = ev[ev["entry_idx"] < len(cal)]
        self._by_idx = {int(i): list(dict.fromkeys(g["code"])) for i, g in ev.groupby("entry_idx")}
        self.skipped: List[dict] = []

    def orders(self, date, panel, holdings: Dict[str, Holding], equity: float) -> Optional[Orders]:
        idx = panel.calendar.get_loc(date)
        sells = [c for c, h in holdings.items() if idx - h.meta.get("entry_idx", idx) >= self.hold_days]
        codes = self._by_idx.get(idx, [])
        buys, meta = {}, {}
        if codes:
            f = self.candidates.frame(date)
            yen = _lot_yen(equity, self.max_positions, self.weight)
            if not f.empty:
                f = f[f["unit_cost"] <= yen]
            pool = [c for c in f.index if c not in holdings] if not f.empty else []
            if self.pick == "random":
                rng = random.Random(f"{self.seed}-{date:%Y%m%d}")
                chosen = rng.sample(pool, min(len(codes), len(pool)))
            else:
                chosen = []
                for c in codes:
                    if c in holdings or c in buys:
                        continue
                    if c in pool:
                        chosen.append(c)
                    else:
                        self.skipped.append({"date": date, "code": c, "reason": "候補条件外（流動性・上場日数・単元価格・データなし）"})
            open_slots = self.max_positions - (len(holdings) - len(sells))
            for c in chosen[:max(open_slots, 0)]:
                buys[c] = yen
                meta[c] = {"entry_idx": idx, "event_date": str(date.date())}
        if not sells and not buys:
            return None
        return Orders(sells=sells, buys=buys, reason=self.name, meta=meta)


@dataclass
class IndexTiming:
    """
    1306 そのものを持つ期間を限る（月末月初だけ、など）。sweep_ticker を空にし、
    data に "1306" を株として入れて使う。保有しない期間は現金。
    mode: "tom"（月末 before 営業日前〜月初 after 営業日目だけ保有）
    """
    name: str = "index_tom"
    code: str = "1306"
    before: int = 1
    after: int = 3
    weight: float = 1.0

    def _in_window(self, cal: pd.DatetimeIndex, i: int) -> bool:
        # 月初から after 営業日以内、または月末まで before 営業日以内
        n_from_start = 0
        k = i
        while k > 0 and cal[k - 1].month == cal[i].month:
            k -= 1
            n_from_start += 1
        n_to_end = 0
        k = i
        while k + 1 < len(cal) and cal[k + 1].month == cal[i].month:
            k += 1
            n_to_end += 1
        return n_from_start < self.after or n_to_end < self.before

    def orders(self, date, panel, holdings, equity) -> Optional[Orders]:
        i = panel.calendar.get_loc(date)
        inside = self._in_window(panel.calendar, i)
        if inside and self.code not in holdings:
            return Orders(buys={self.code: equity * self.weight}, reason=f"{self.name} in")
        if not inside and self.code in holdings:
            return Orders(sells=[self.code], reason=f"{self.name} out")
        return None


class ExcludeTrades:
    """
    別の戦略をそのまま動かし、指定した (銘柄, 判断日) の買いだけを出さない（その枠は 1306 のまま）。
    「実現損益の上位 3 件の取引が無かったら」の再実行に使う（docs/research/hypotheses.md 3d 章）。
    判断日はエンジンが保有の meta["signal_date"] に残す。
    """

    def __init__(self, inner, banned):
        self.inner = inner
        self.banned = {(str(c), pd.Timestamp(d)) for c, d in banned}
        self.name = f"{getattr(inner, 'name', type(inner).__name__)} (除外 {len(self.banned)} 件)"

    def orders(self, date, panel, holdings, equity) -> Optional[Orders]:
        o = self.inner.orders(date, panel, holdings, equity)
        if o is None:
            return None
        buys = {c: y for c, y in o.buys.items() if (c, date) not in self.banned}
        if not o.sells and not buys:
            return None
        return Orders(sells=o.sells, buys=buys, reason=o.reason, meta=o.meta)
