#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 2 期の合格基準（docs/research/hypotheses.md 3d 章）の判定一式

1 つの条件 × 1 期間について次を出す:
- 税引後の 1306 比（期末一括課税）と、売らない版どうしの比較（戦略は期末に清算しない、1306 は売却益の税なし）
- 対 1306 の日次超過リターン: シャープ・PSR(>0)・ブロックブートストラップ（ブロック 20 日、10,000 回）
- ランダム比較の分布の中の位置、超過リターン版の DSR（V[SR] はランダムの超過シャープの分散）
- 実現損益の上位 3 件を除いた再実行、取引の中央値リターン・勝率
- コスト感度（片道 0 / 0.05 / 0.10 / 0.20 / 0.30%、流動性によらず一律）
- 運用性: 1 回の売買代金 ÷ 平均売買代金の最大値、月の売買回数の最大値

strategy_factory(seed, pick) は毎回新しい戦略を返す関数（戦略は状態を持つので使い回さない）。
pick=None は本番の条件、"random" などはランダム比較。
"""

from dataclasses import replace
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..strategy.rules import ExcludeTrades
from .rules_engine import RulesConfig, RulesEngine
from .stats import (_kurtosis, _skew, block_bootstrap_outperform, expected_max_sharpe,
                    probabilistic_sharpe_ratio, random_rank)

COST_LEVELS = (0.0, 0.0005, 0.001, 0.002, 0.003)


def cost_key(level: float) -> str:
    return f"excess_cost_{level * 100:.2f}%"


def active_returns(res: Dict) -> pd.Series:
    """戦略の日次リターン − 1306 全額保有の日次リターン"""
    s = res["history"]["total_value"].pct_change()
    b = res["benchmark"].history["total_value"].reindex(s.index).pct_change()
    return (s - b).dropna()


def _sr(x: np.ndarray) -> float:
    sd = x.std()
    return float(x.mean() / sd) if sd > 0 else 0.0


def active_stats(active: pd.Series) -> Dict[str, float]:
    x = active.to_numpy()
    sr = _sr(x)
    sk, ku = (_skew(x), _kurtosis(x)) if x.std() > 0 else (0.0, 3.0)
    bb = block_bootstrap_outperform(active, block_len=20, n_boot=10_000, seed=0)
    return {"active_sr": sr, "active_skew": sk, "active_kurt": ku, "T": len(x),
            "psr": probabilistic_sharpe_ratio(sr, 0.0, len(x), sk, ku),
            "p_boot": bb["p_outperform"], "excess_ann": bb.get("mean_ann", float("nan"))}


def trade_stats(res: Dict) -> Dict[str, float]:
    c = res["closed"]
    if len(c) == 0:
        return {"n_closed": 0, "median_ret": float("nan"), "win_rate": float("nan")}
    ret = c["pnl"] / (c["avg_price"] * c["shares"])
    return {"n_closed": int(len(c)), "median_ret": float(ret.median()), "win_rate": float((c["pnl"] > 0).mean())}


def top_trades(res: Dict, k: int = 3) -> List[tuple]:
    """実現損益（税引前）の上位 k 件の (銘柄, 判断日)"""
    c = res["closed"]
    if len(c) == 0 or "signal_date" not in c:
        return []
    return [(r["code"], pd.Timestamp(r["signal_date"])) for _, r in c.nlargest(k, "pnl").iterrows()]


def operability(res: Dict, panel, sweep: str = "1306") -> Dict[str, float]:
    t = res["trades"]
    t = t[t["code"] != sweep] if len(t) else t
    if len(t) == 0:
        return {"max_participation": 0.0, "max_trades_month": 0}
    turn = np.array([panel.avg_turnover.at[d, c] if c in panel.avg_turnover.columns else np.nan
                     for d, c in zip(t["date"], t["code"])], dtype=float)
    part = t["amount"].to_numpy() / turn
    per_month = t.groupby(pd.to_datetime(t["date"]).dt.to_period("M")).size()
    return {"max_participation": float(np.nanmax(part)) if np.isfinite(part).any() else float("nan"),
            "max_trades_month": int(per_month.max())}


def with_cost(cfg: RulesConfig, level: float) -> RulesConfig:
    return replace(cfg, execution=replace(cfg.execution, slippage_liquid=level, slippage_illiquid=level))


def evaluate(strategy_factory: Callable, cfg: RulesConfig, panel, etf, seeds: int = 20,
             n_trials: int = 1, random_pick: str = "random") -> Dict:
    """1 条件 × 1 期間の判定一式。戻り値: row（要約の 1 行）、res（本番の結果）、random_excess"""
    run = lambda c, s: RulesEngine(c, s, panel, etf).run()  # noqa: E731
    res = run(cfg, strategy_factory(0, None))
    m = res["metrics"]
    bench = res["benchmark"]
    row = {"start": m["start"], "end": m["end"],
           "final_after_tax": m["final_value_after_tax"], "bench_after_tax": m["benchmark_final_after_tax"],
           "excess": m["excess_vs_benchmark"], "max_dd": m["max_drawdown"], "bench_dd": m["benchmark_max_drawdown"],
           "dd_worse_pt": (m["benchmark_max_drawdown"] - m["max_drawdown"]) * 100,
           "stock_trades": m["stock_trades"], "tax_paid": m["tax_paid"], "avg_stock_exposure": m["avg_stock_exposure"],
           **active_stats(active_returns(res)), **trade_stats(res), **operability(res, panel, cfg.sweep_ticker)}

    # 売らない版どうし（戦略は期末に清算しない＝含み益に課税しない、1306 は売却益の税を引く前の評価額）
    hold = run(replace(cfg, liquidate_at_end=False), strategy_factory(0, None))
    row["final_no_sell"] = float(hold["history"]["total_value"].iloc[-1])
    row["bench_no_sell"] = float(bench.history["total_value"].iloc[-1])
    row["excess_no_sell"] = row["final_no_sell"] - row["bench_no_sell"]

    # 実現損益の上位 3 件を買わなかった場合
    banned = top_trades(res, 3)
    row["excess_ex_top3"] = run(cfg, ExcludeTrades(strategy_factory(0, None), banned))["metrics"]["excess_vs_benchmark"]
    row["top3"] = ";".join(f"{c}@{d.date()}" for c, d in banned)

    # コスト感度
    for lv in COST_LEVELS:
        row[cost_key(lv)] = run(with_cost(cfg, lv), strategy_factory(0, None))["metrics"]["excess_vs_benchmark"]

    # ランダム比較と超過リターン版 DSR
    rnd_excess, rnd_sr, rnd_trades = [], [], []
    for seed in range(seeds):
        r = run(cfg, strategy_factory(seed, random_pick))
        rnd_excess.append(r["metrics"]["excess_vs_benchmark"])
        rnd_trades.append(r["metrics"]["stock_trades"])
        rnd_sr.append(_sr(active_returns(r).to_numpy()))
    if rnd_excess:
        rk = random_rank(m["excess_vs_benchmark"], rnd_excess)
        row.update({"random_percentile": rk["percentile"], "random_median": rk["median"], "random_p90": rk["p90"],
                    "random_trades_median": float(np.median(rnd_trades))})
    if len(rnd_sr) > 1:
        sr_star = expected_max_sharpe(n_trials, float(np.var(rnd_sr, ddof=1)))
        row["dsr_sr_star"] = sr_star
        row["dsr_active"] = probabilistic_sharpe_ratio(row["active_sr"], sr_star, row["T"],
                                                       row["active_skew"], row["active_kurt"])
    row["n_trials"] = n_trials
    return {"row": row, "res": res, "random_excess": rnd_excess}


def verdict(row: Dict) -> Dict[str, bool]:
    """3d 章の基準ごとの合否（1 期間分）"""
    part = row.get("max_participation", 0.0)
    return {
        "1_超え": row["excess"] > 0,
        "4a_ランダム上位10%": row.get("random_percentile", 0.0) >= 0.9,
        "4b_PSR": row["psr"] >= 0.95,
        "4c_ブートストラップ": row["p_boot"] >= 0.95,
        "5_DD": row["dd_worse_pt"] <= 10,
        "5_上位3除外": row["excess_ex_top3"] > 0,
        "6_参加率1%": bool(part <= 0.01) if np.isfinite(part) else True,
        "7_コスト0.20%": row[cost_key(0.002)] > 0,
    }
