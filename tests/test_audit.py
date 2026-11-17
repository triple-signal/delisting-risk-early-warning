"""감사 신호: 감사보수·시간 금액 정리, 당기·전기 구분, 감사의견·감사인 표기 정리"""
import math

import pytest

from src.audit import _amount, _auditor, _opinion, _split_periods, _sum


@pytest.mark.parametrize("cell, expected", [
    ("1,234", 1234),
    ("120 백만원", 120e6),
    ("3억원", 3e8),
    ("500천원", 500e3),
    ("100\n200", 300),           # 칸 안 여러 숫자는 합산
    ("-", math.nan),
])
def test_amount(cell, expected):
    v = _amount(cell)
    assert (math.isnan(v) and math.isnan(expected)) or v == pytest.approx(expected)


@pytest.mark.parametrize("cell, expected", [
    ("150", 150e6),              # 1만 미만 → 백만원 단위로 추정
    ("150,000", 150e6),          # 1천만 미만 → 천원 단위
    ("150,000,000", 150e6),      # 그 이상 → 원
    ("150 백만원", 150e6),        # 단위가 적혀 있으면 추정하지 않음
])
def test_fee_unit_inference(cell, expected):
    assert _sum([{"fee": cell}], ["fee"], fee=True) == pytest.approx(expected)


def test_sum_uses_fallback_column_for_old_format():
    rows = [{"신형식": "", "구형식": "10"}, {"신형식": "5", "구형식": "99"}]
    assert _sum(rows, ["신형식", "구형식"]) == 15


def test_split_periods_by_fiscal_term():
    rows = [{"bsns_year": "제12기(전기)", "v": 1}, {"bsns_year": "제13기(당기)", "v": 2},
            {"bsns_year": "제11기(전전기)", "v": 3}]
    cur, prev = _split_periods(rows)
    assert [r["v"] for r in cur] == [2]
    assert [r["v"] for r in prev] == [1]


def test_split_periods_by_label_when_no_term():
    rows = [{"bsns_year": "당기", "v": 1}, {"bsns_year": "전기", "v": 2}, {"bsns_year": "전전기", "v": 3}]
    cur, prev = _split_periods(rows)
    assert [r["v"] for r in cur] == [1]
    assert [r["v"] for r in prev] == [2]


@pytest.mark.parametrize("text, expected", [
    ("적정", "적정"), ("한정의견", "한정"), ("부적정", "부적정"), ("의견 거절", "의견거절"),
])
def test_opinion(text, expected):
    assert _opinion(text) == expected


def test_auditor_name_normalized():
    assert _auditor("삼일 회계법인") == _auditor("(주)삼일") == "삼일"
