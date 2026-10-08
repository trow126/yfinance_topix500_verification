#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バックテスト結果の統計的な評価

- probabilistic_sharpe_ratio: 観測したシャープレシオが基準値 sr_star を上回る確率（Bailey & López de Prado 2012）
- deflated_sharpe_ratio: 試した条件の数（N）で割り引いた PSR（Bailey & López de Prado 2014）
  sr_star = sqrt(V[SR]) * ((1-γ) Z^{-1}(1-1/N) + γ Z^{-1}(1-1/(N e)))、γ はオイラー・マスケローニ定数
- random_rank: ランダム選定の分布の中で戦略がどの位置にあるか（上位 10% に入るか）

シャープレシオは日次（年率換算しない）で扱い、T は日数。
"""

import math
from statistics import NormalDist
from typing import Dict, Iterable

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329
_N = NormalDist()


class norm:  # scipy.stats.norm の代わり（標準ライブラリだけで動かす）
    @staticmethod
    def cdf(z: float) -> float:
        return _N.cdf(z)

    @staticmethod
    def ppf(p: float) -> float:
        return _N.inv_cdf(p)


def _skew(x: np.ndarray) -> float:
    m = x.mean()
    s = x.std()
    return float(((x - m) ** 3).mean() / s ** 3) if s > 0 else 0.0


def _kurtosis(x: np.ndarray) -> float:
    """尖度（正規分布で 3）"""
    m = x.mean()
    s = x.std()
    return float(((x - m) ** 4).mean() / s ** 4) if s > 0 else 3.0


def daily_sharpe(values: pd.Series) -> Dict[str, float]:
    """評価額の系列から日次シャープレシオ・歪度・尖度・日数を出す"""
    r = values.dropna().pct_change().dropna()
    if len(r) < 3 or r.std() == 0:
        return {"sr": 0.0, "skew": 0.0, "kurt": 3.0, "T": len(r)}
    x = r.to_numpy()
    return {"sr": float(r.mean() / r.std()), "skew": _skew(x), "kurt": _kurtosis(x), "T": int(len(r))}


def probabilistic_sharpe_ratio(sr: float, sr_star: float, T: int, skew_: float = 0.0, kurt: float = 3.0) -> float:
    if T <= 1:
        return 0.0
    denom = math.sqrt(max(1 - skew_ * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    z = (sr - sr_star) * math.sqrt(T - 1) / denom
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """N 回試した中で偶然出る最大シャープレシオの期待値"""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    n = float(n_trials)
    return math.sqrt(var_sr) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n) + EULER_GAMMA * norm.ppf(1 - 1 / (n * math.e)))


def deflated_sharpe_ratio(sr: float, trial_sharpes: Iterable[float], T: int,
                          skew_: float = 0.0, kurt: float = 3.0) -> Dict[str, float]:
    """
    sr: 評価する戦略の日次シャープレシオ
    trial_sharpes: 試した全条件の日次シャープレシオ（分散と個数を使う）
    """
    trials = [float(s) for s in trial_sharpes]
    n = len(trials)
    var_sr = float(np.var(trials, ddof=1)) if n > 1 else 0.0
    sr_star = expected_max_sharpe(n, var_sr)
    return {"n_trials": n, "var_sr": var_sr, "sr_star": sr_star,
            "dsr": probabilistic_sharpe_ratio(sr, sr_star, T, skew_, kurt)}


def block_bootstrap_outperform(active: pd.Series, block_len: int = 20, n_boot: int = 10_000,
                               seed: int = 0) -> Dict[str, float]:
    """
    対ベンチマークの日次超過リターン系列を循環ブロックブートストラップで再抽出し、
    「期間全体の累積超過リターンが正になる確率」と、超過平均の信頼区間を出す。

    - ブロック長は事前に固定する（既定 20 営業日: 月次リバランスの周期に合わせる）
    - 累積は (1 + r_strategy) / (1 + r_bench) の比ではなく、超過リターンの単純合計で近似する
    """
    x = active.dropna().to_numpy()
    T = len(x)
    if T < block_len * 2:
        return {"T": T, "p_outperform": float("nan"), "mean_lo": float("nan"), "mean_hi": float("nan")}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(T / block_len))
    starts = rng.integers(0, T, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block_len)[None, None, :]) % T
    samples = x[idx.reshape(n_boot, -1)[:, :T]]
    sums = samples.sum(axis=1)
    means = samples.mean(axis=1)
    return {"T": T, "block_len": block_len, "n_boot": n_boot,
            "p_outperform": float((sums > 0).mean()),
            "mean_lo": float(np.quantile(means, 0.05) * 252), "mean_hi": float(np.quantile(means, 0.95) * 252),
            "mean_ann": float(x.mean() * 252)}


def random_rank(value: float, random_values: Iterable[float]) -> Dict[str, float]:
    """ランダム選定の分布の中での位置（percentile: 上位何%か。上位 10% = percentile >= 0.9）"""
    xs = np.array(sorted(float(v) for v in random_values))
    if len(xs) == 0:
        return {"n_random": 0, "percentile": float("nan"), "median": float("nan"), "p90": float("nan")}
    pct = float((xs < value).mean())
    return {"n_random": int(len(xs)), "percentile": pct, "median": float(np.median(xs)),
            "p10": float(np.quantile(xs, 0.1)), "p90": float(np.quantile(xs, 0.9))}
