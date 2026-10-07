#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有報「株主に対する特典」の読み取りテスト（実際の有報の文面をもとにした例）
"""

import pandas as pd

from src.data.edinet_benefits import parse_benefit, record_date_in_month

HEAD = "事業年度４月１日から３月31日まで基準日３月31日剰余金の配当の基準日９月30日３月31日"


def test_month_end_and_min_shares():
    b = parse_benefit(HEAD + "株主に対する特典毎年３月31日現在、100株を所有する株主に対して1,500円相当の当社製品、"
                             "200株以上を所有する株主に対して3,000円相当の当社製品を贈呈しております。")
    assert b.has_benefit
    assert b.record_dates == [(3, 0)]
    assert b.min_shares == 100
    assert b.continuous_holding == "none"


def test_month_list_and_validity_period_ignored():
    b = parse_benefit(HEAD + "株主に対する特典３月末日及び９月末日現在において、1単元以上保有している株主に対して、"
                             "６月下旬及び12月上旬に優待カードを発行しております。有効期限 翌年７月末日")
    assert b.record_dates == [(3, 0), (9, 0)]
    assert b.min_shares == 100


def test_circled_numbers_and_mid_month_date():
    b = parse_benefit(HEAD + "株主に対する特典 毎年２月20日現在の株主名簿に記録された株主に対し "
                             "①100株以上保有の株主に1,000円相当 ②1,000株以上保有の株主に10,000円相当")
    assert b.record_dates == [(2, 20)]
    assert b.min_shares == 100  # 「①100株」を1100株と読まない


def test_continuous_holding():
    required = parse_benefit(HEAD + "株主に対する特典 毎年９月30日現在の株主名簿に記載された100株以上所有"
                                    "かつ１年以上継続保有の株主。")
    bonus = parse_benefit(HEAD + "株主に対する特典 毎年３月末日現在に100株以上ご保有の株主 "
                                 "継続保有年数5年未満の株主様 1,000円 長期保有者優遇制度継続保有年数5年以上 2,000円")
    assert required.continuous_holding == "required"
    assert bonus.continuous_holding == "bonus"


def test_no_benefit():
    b = parse_benefit(HEAD + "株主に対する特典 該当事項はありません。（注）当社定款の定めにより、単元未満株主は、"
                             "会社法第189条第２項各号に掲げる権利以外の権利を有しておりません。")
    assert not b.has_benefit


def test_record_date_in_month():
    b = parse_benefit(HEAD + "株主に対する特典 毎年２月20日及び８月末日現在の株主名簿に記載された100株以上")
    assert record_date_in_month(b, pd.Period("2023-02")) == pd.Timestamp("2023-02-20")
    assert record_date_in_month(b, pd.Period("2023-08")) == pd.Timestamp("2023-08-31")
    assert record_date_in_month(b, pd.Period("2023-03")) is None
