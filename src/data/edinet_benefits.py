#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有価証券報告書「株式事務の概要」の「株主に対する特典」欄から優待の条件を読み取る

文章で書かれているため、次の項目をパターンで抽出する（完全ではない）:
- 優待の基準日（月・日）: 「毎年３月末」「９月30日現在」「３月、９月の各末日」など
- 優待がもらえる最低株数: 「100株以上」「１単元」
- 継続保有の条件: 「１年以上継続保有」「半年以上前から継続保有」など
"""

import calendar
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

# 単元未満株式の権利についての定型文（優待とは無関係）
_BOILERPLATE = re.compile(r"(（注）|\(注\)|注\)|定款の定め|単元未満株主|単元未満株式を有する).*?(会社法|権利)")
# 基準日らしい日付の直後に来る語（有効期間・発送時期の日付を除くため）
# 「２月20日及び８月末日現在」のように別の日付と並んでいる場合も基準日とみなす
# 「(4月30日)の株主名簿」「5月末日の最終の株主名簿」も拾う
_RECORD_CONTEXT = (r"(?=\)?\s*(?:現在|時点|の株主名簿|の最終|における|を基準日|を割当基準日|に.{0,6}株主名簿"
                   r"|の各末日|の株主|(?:及び|および|、|・|と)\s*\d{1,2}月))")
_DATE = re.compile(r"(\d{1,2})月(\d{1,2})日" + _RECORD_CONTEXT)
_MONTH_END = re.compile(r"(\d{1,2})月末(?:日)?" + _RECORD_CONTEXT)
# 「３月、９月の各末日」「３月末日及び９月末日現在」
_MONTH_LIST_END = re.compile(
    r"((?:\d{1,2}月(?:末日?)?\s*(?:、|及び|および|と|・|,)\s*)+\d{1,2}月)\s*(?:の)?(?:各)?末")
# NFKC後は括弧が半角になる。「100株(1単元)以上」「100株を所有する」も拾う
_SHARES = re.compile(r"([\d,]+)株\s*(?:\([^)]{0,10}\))?\s*(?:以上|～|~|から|を(?:所有|保有))")
_UNIT = re.compile(r"(\d+)単元\s*(?:\([\d,]+株\))?\s*以上")
# 丸数字（①など）はNFKCで数字になり「①100株」が「1100株」になるので先に消す
_CIRCLED = {cp: " " for cp in range(0x2460, 0x2474)}
_CONTINUOUS = re.compile(r"(継続|連続)(?:して)?.{0,8}(保有|所有|記録|記載)|(\d+|半)年以上.{0,6}(継続|保有|所有)")
_TIERED = re.compile(r"年未満|初年度|年目|未満の株主")


@dataclass
class Benefit:
    has_benefit: bool
    record_dates: List[Tuple[int, int]] = field(default_factory=list)  # (月, 日)。末日は0
    min_shares: Optional[int] = None
    continuous_holding: str = "none"   # none / required / bonus（長期保有で増えるだけ）
    text: str = ""


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", (text or "").translate(_CIRCLED))


def benefit_section(text: str) -> str:
    """「株主に対する特典」以降の本文（定型の注記は除く）"""
    t = _normalize(text)
    i = t.find("株主に対する特典")
    if i < 0:
        return ""
    section = t[i + len("株主に対する特典"):]
    return _BOILERPLATE.sub(" ", section).strip()


def parse_benefit(text: str, unit_shares: int = 100) -> Benefit:
    section = benefit_section(text)
    head = section[:20]
    if not section or re.match(r"^[\s【】]*(該当事項|該当なし|なし|―|-|─|－)", head):
        return Benefit(has_benefit=False, text=section[:300])

    dates = set()
    for m in _MONTH_LIST_END.finditer(section):
        for month in re.findall(r"(\d{1,2})月", m.group(1)):
            dates.add((int(month), 0))
    for m in _MONTH_END.finditer(section):
        dates.add((int(m.group(1)), 0))
    for m in _DATE.finditer(section):
        month, day = int(m.group(1)), int(m.group(2))
        if day >= calendar.monthrange(2023, month)[1] - (1 if month == 2 else 0):
            day = 0  # 月末日
        dates.add((month, day))
    dates = {(m, d) for m, d in dates if 1 <= m <= 12}

    shares = [int(s.replace(",", "")) for s in _SHARES.findall(section)]
    shares += [int(u) * unit_shares for u in _UNIT.findall(section)]
    shares = [s for s in shares if s >= unit_shares]  # 単元未満の数字は誤検出
    min_shares = min(shares) if shares else None

    continuous = "none"
    if _CONTINUOUS.search(section):
        continuous = "bonus" if _TIERED.search(section) else "required"

    return Benefit(True, sorted(dates), min_shares, continuous, section[:300])


def record_date_in_month(benefit: Benefit, period: pd.Period) -> Optional[pd.Timestamp]:
    """その月の優待基準日（暦日）。該当がなければNone"""
    days = [d for m, d in benefit.record_dates if m == period.month]
    if not days:
        return None
    day = min(days) if 0 not in days else 0  # 月途中の基準日を優先
    if day == 0:
        return period.to_timestamp(how="end").normalize()
    return pd.Timestamp(period.year, period.month, day)


def load_benefits(path: str) -> pd.DataFrame:
    """fetch_edinet_benefits.py の出力を読み込み、解析結果の列を付ける"""
    df = pd.read_csv(path, sep="\t", dtype={"code": str}, parse_dates=["submitted"])
    df["text"] = df["text"].fillna("")
    df["benefit"] = df["text"].map(parse_benefit)
    return df.sort_values(["code", "submitted"]).reset_index(drop=True)
