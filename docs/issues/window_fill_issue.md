# 窓埋め判定問題と解決策

## 問題の概要

権利落ち前価格がエントリー価格より低く設定されることで、権利落ち日にすぐに「窓埋め達成」と判定されてしまう問題が発生していました。

## 原因

### 1. エントリータイミングと権利落ち前価格の関係
- エントリー日: 権利確定日の3営業日前
- 権利落ち前価格: 権利落ち日の前営業日の価格
- 場合によってはエントリー日の方が権利落ち前日より後になる

### 2. 価格データ取得の問題
- BusinessDayCalculatorで計算した日付と実際の取引日がずれる可能性

## 部分的な解決策

### 1. 権利落ち前価格の取得改善
実際の価格データから前営業日を取得するように修正：

```python
# 実際の価格データから前営業日を取得
price_data = self.data_manager.get_price_data(ticker)
if price_data is not None and not price_data.empty:
    dates = price_data.index.tolist()
    try:
        current_idx = next(i for i, d in enumerate(dates) if d.date() == current_date.date())
        if current_idx > 0:
            pre_ex_date = dates[current_idx - 1]
            pre_ex_price = price_data.iloc[current_idx - 1]["Close"]
```

### 2. 最低保有期間の追加
dividend_strategy.pyで窓埋め判定に最低保有期間（3営業日）を追加：

```python
# 最低保有期間（3営業日）を追加
min_holding_days = 3
if self.exit_config.take_profit_on_window_fill and current_price >= pre_ex_price and holding_days >= min_holding_days:
```

## 今後の改善案

1. **エントリータイミングの最適化**
   - 権利落ち日からの逆算でエントリー日を決定
   - より柔軟なエントリー条件の設定

2. **窓埋め判定の改善**
   - 配当落ち幅を考慮した判定
   - 複数日の価格推移を考慮

3. **pre_ex_priceの定義明確化**
   - エントリー時の最高値を使用
   - または権利落ち前日の終値を厳密に使用
