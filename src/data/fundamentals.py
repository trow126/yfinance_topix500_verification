#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
J-Quants の決算短信サマリー（fins/summary）から、判断日に分かっていた財務指標を作る（H10、hypotheses.md 3g 章）

開示が分かった日（known_date）:
- 開示日の取引時間中に出たものは開示日の引け後に分かったとみなす。判断日 t に使えるのは known_date < t のものだけ
  （判断日の前日までに開示されたもの）。
- 開示時刻が 15:00 以降（2024-11-05 以降は 15:30 以降）のものは翌営業日に分かったものとする。
  known_date はこの「翌営業日」。どちらの場合も判断日 t > known_date を求めるので、引け後の開示は翌々営業日以降の判断に使う。
  訂正開示は訂正の開示日から使う（行ごとに開示日で付けるので自然にそうなる）。

判断日ごとに銘柄 → 次の列:
- np_pos3: 直近 3 期の通期実績（FYFinancialStatements）の当期純利益がすべて正（3 期そろわなければ False）
- eqar: 直近の決算短信（通期・四半期）の自己資本比率
- prev_div: 直近の通期実績の年間配当（DivAnn）
- fdiv: 今期（直近の通期実績の翌期）の年間配当の会社予想。通期短信の NxFDivAnn、
        その後の四半期短信・配当予想の修正の FDivAnn のうち最新のもの。空欄（未定など）は NaN
J-Quants の配当は開示時点の株数ベース（分割で遡及調整しない）。
"""

from typing import Optional

import numpy as np
import pandas as pd

LATE_CUTOFF_CHANGE = pd.Timestamp("2024-11-05")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace("", np.nan), errors="coerce")


class Fundamentals:
    def __init__(self, summary: pd.DataFrame, calendar: pd.DatetimeIndex):
        d = summary.copy()
        d["code"] = d["Code"].astype(str).str[:4]
        d["disc_date"] = pd.to_datetime(d["DiscDate"])
        t = d["DiscTime"].fillna("").str.slice(0, 5)
        cutoff = np.where(d["disc_date"] >= LATE_CUTOFF_CHANGE, "15:30", "15:00")
        late = (t >= cutoff) & (t != "")
        # 開示日以降の最初の営業日（休日開示は翌営業日）。引け後なら更にその翌営業日
        pos = calendar.searchsorted(d["disc_date"].to_numpy(), side="left") + late.astype(int).to_numpy()
        d = d[pos < len(calendar)].copy()
        d["known_idx"] = pos[pos < len(calendar)]
        d["fy_end"] = pd.to_datetime(d["CurFYEn"], errors="coerce")
        d["is_fs"] = d["DocType"].str.contains("FinancialStatements", na=False)
        d["is_fy"] = d["is_fs"] & (d["CurPerType"] == "FY")
        for col in ("NP", "EqAR", "DivAnn", "FDivAnn", "NxFDivAnn"):
            d[col] = _num(d[col]) if col in d else np.nan
        self.calendar = calendar
        self.rows = d.sort_values(["known_idx", "DiscTime"]).reset_index(drop=True)

    def frame(self, date: pd.Timestamp) -> pd.DataFrame:
        i = self.calendar.get_loc(date)
        d = self.rows[self.rows["known_idx"] < i]
        fy = d[d["is_fy"]].drop_duplicates(["code", "fy_end"], keep="last")  # 同じ期の訂正は最新を使う
        fy = fy.sort_values(["code", "fy_end"])
        last3 = fy.groupby("code").tail(3)
        g = last3.groupby("code")
        np_pos3 = (g["NP"].apply(lambda s: bool(len(s) == 3 and (s > 0).all())))
        latest_fy = fy.groupby("code").tail(1).set_index("code")
        out = pd.DataFrame({"np_pos3": np_pos3})
        out["prev_div"] = latest_fy["DivAnn"]
        out["prev_fy_end"] = latest_fy["fy_end"]
        out["prev_known_idx"] = latest_fy["known_idx"]
        fs = d[d["is_fs"]].groupby("code").tail(1).set_index("code")
        out["eqar"] = fs["EqAR"]
        # 今期の配当予想
        f1 = latest_fy[["NxFDivAnn", "known_idx"]].rename(columns={"NxFDivAnn": "fdiv"})
        f1["order"] = f1["known_idx"]
        later = d.merge(latest_fy[["fy_end"]].rename(columns={"fy_end": "prev_fy_end"}), left_on="code", right_index=True)
        later = later[(later["fy_end"] > later["prev_fy_end"]) & (later["fy_end"] <= later["prev_fy_end"] + pd.DateOffset(months=13))]
        later = later[later["FDivAnn"].notna()]
        f2 = later.groupby("code").tail(1).set_index("code")[["FDivAnn", "known_idx"]].rename(columns={"FDivAnn": "fdiv"})
        f = pd.concat([f1, f2.assign(order=f2["known_idx"] + 0.5)])
        f = f.sort_values("order").groupby(level=0).tail(1)
        out["fdiv"] = f["fdiv"]
        out["np_pos3"] = out["np_pos3"].fillna(False).astype(bool)
        return out

    def passes(self, date: pd.Timestamp, min_eqar: float = 0.30) -> pd.DataFrame:
        """3g 章の財務フィルタ（3 つすべて）を満たす銘柄の frame"""
        f = self.frame(date)
        ok = f["np_pos3"] & (f["eqar"] >= min_eqar) & f["fdiv"].notna() & f["prev_div"].notna() & (f["fdiv"] >= f["prev_div"])
        return f[ok]


def _first(d: pd.DataFrame, cols) -> pd.Series:
    out = pd.Series(np.nan, index=d.index)
    for c in cols:
        if c in d:
            out = out.fillna(_num(d[c]))
    return out


def earnings_events(summary: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """
    H11（hypotheses.md 3h 章）のイベント。列: date（開示が分かった日）, code, kind（"revision_up" / "q2_progress"）

    - 当期純利益の今期の会社予想: FNP（空欄なら FNCNP）。通期短信の来期予想 NxFNp（空欄なら NxFNCNP）は翌期の予想として扱う
    - 直前の予想 = 同じ決算期について、それより前に開示された予想（短信・業績予想の修正のどれでも）の最新
    - revision_up: 決算短信（FinancialStatements）で、今期予想 ≥ 直前の予想 × 1.10 かつ直前の予想 > 0
    - q2_progress: 第 2 四半期の決算短信で、累計の当期純利益 ÷ 今期予想 ≥ 0.6、今期予想 > 0、直前の予想があり今期予想 ≥ 直前の予想
    - 開示が分かった日: 取引時間中は開示日、15:00（2024-11-05 以降は 15:30）以降と休日は翌営業日
    """
    d = summary.copy()
    d["code"] = d["Code"].astype(str).str[:4]
    d["disc_date"] = pd.to_datetime(d["DiscDate"])
    t = d["DiscTime"].fillna("").str.slice(0, 5)
    cutoff = np.where(d["disc_date"] >= LATE_CUTOFF_CHANGE, "15:30", "15:00")
    late = ((t >= cutoff) & (t != "")).astype(int).to_numpy()
    pos = calendar.searchsorted(d["disc_date"].to_numpy(), side="left") + late
    d = d[pos < len(calendar)].copy()
    d["date"] = calendar[pos[pos < len(calendar)]]
    d["is_fs"] = d["DocType"].str.contains("FinancialStatements", na=False)
    d["np"] = _first(d, ["NP", "NCNP"])
    cur = d[["code", "date", "DiscTime", "DocType", "CurPerType", "is_fs", "np"]].copy()
    cur["fy"] = pd.to_datetime(d["CurFYEn"], errors="coerce")
    cur["fc"] = _first(d, ["FNP", "FNCNP"])
    nxt = d[["code", "date", "DiscTime", "DocType", "CurPerType", "is_fs", "np"]].copy()
    nxt["fy"] = pd.to_datetime(d["NxtFYEn"], errors="coerce")
    nxt["fc"] = _first(d, ["NxFNp", "NxFNCNP"])
    nxt["is_fs"] = False  # 来期予想の初出は「修正」ではない
    nxt["CurPerType"] = "next"
    f = pd.concat([cur, nxt]).dropna(subset=["fy", "fc"])
    f = f.sort_values(["code", "fy", "date", "DiscTime"]).reset_index(drop=True)
    f["prev_fc"] = f.groupby(["code", "fy"])["fc"].shift(1)
    fs = f[f["is_fs"]]
    up = fs[(fs["prev_fc"] > 0) & (fs["fc"] >= fs["prev_fc"] * 1.10)]
    q2 = fs[(fs["CurPerType"] == "2Q") & (fs["fc"] > 0) & (fs["np"] / fs["fc"] >= 0.6)
            & fs["prev_fc"].notna() & (fs["fc"] >= fs["prev_fc"])]
    ev = pd.concat([up.assign(kind="revision_up"), q2.assign(kind="q2_progress")])
    return ev[["date", "code", "kind", "fc", "prev_fc", "np"]].drop_duplicates(["date", "code", "kind"]).reset_index(drop=True)
