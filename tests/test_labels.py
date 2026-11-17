"""상장폐지 라벨: KIND 폐지 사유 분류 규칙 (research_design.md 3절)"""
import pytest

from src.labels import classify


@pytest.mark.parametrize("reason, expected", [
    ("감사의견 거절(감사범위 제한)", "부실:감사의견"),
    ("상장적격성 실질심사 결과 기업의 계속성, 경영의 투명성 등을 종합적으로 고려", "부실:실질심사"),
    ("최종부도 발생", "부실:부도·파산"),
    ("사업보고서 미제출", "부실:보고서미제출"),
    ("자본잠식률 50% 이상 2년 연속", "부실:재무요건"),
    ("시가총액 미달", "보류:시장요건"),
    ("해산 사유 발생", "보류:해산"),
    ("흡수합병", "제외:비부실"),
    ("유가증권시장 이전상장", "제외:비부실"),
    ("기타", "미분류"),
])
def test_classify_reason(reason, expected):
    assert classify(reason, "테스트기업") == expected


def test_spac_excluded_before_reason_rules():
    assert classify("감사의견 거절", "테스트기업인수목적3호") == "제외:스팩"
    assert classify("존속기간 만료", "테스트스팩1호") == "제외:스팩"


def test_spaces_in_reason_ignored():
    assert classify("감 사 의 견 거절", "테스트기업") == "부실:감사의견"
