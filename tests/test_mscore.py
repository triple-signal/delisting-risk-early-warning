"""재무 신호: Beneish M-Score 계정 탐색과 계산"""
import math

import pandas as pd
import pytest

from src.mscore import COEF, NEUTRAL, THRESHOLD, _clean_name, compute_mscore, extract_items


def fs_rows(cur, prev):
    """DART 재무제표 원본 형태의 가짜 표. cur·prev = {항목: 금액}"""
    spec = {   # 항목: (sj_div, account_id, account_nm)
        "매출액": ("IS", "ifrs-full_Revenue", "매출액"),
        "매출원가": ("IS", "ifrs-full_CostOfSales", "매출원가"),
        "판관비": ("IS", "-표준계정코드 미사용-", "판매비와관리비"),      # 계정ID 없이 계정명으로 찾는 경우
        "당기순이익": ("CIS", "ifrs-full_ProfitLoss", "당기순이익(손실)"),
        "매출채권": ("BS", "ifrs-full_CurrentTradeReceivables", "매출채권"),
        "유동자산": ("BS", "ifrs-full_CurrentAssets", "유동자산"),
        "유형자산": ("BS", "ifrs-full_PropertyPlantAndEquipment", "유형자산"),
        "자산총계": ("BS", "ifrs-full_Assets", "자산총계"),
        "부채총계": ("BS", "ifrs-full_Liabilities", "부채총계"),
        "영업활동현금흐름": ("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities", "영업활동현금흐름"),
        "감가상각비": ("CF", "-표준계정코드 미사용-", "  2. 감가상각비"),   # 앞 번호·띄어쓰기 섞인 계정명
    }
    rows = []
    for item, (sj, aid, nm) in spec.items():
        if item in cur:
            rows.append({"sj_div": sj, "account_id": aid, "account_nm": nm,
                         "thstrm_amount": f"{cur[item]:,}", "frmtrm_amount": f"{prev[item]:,}"})
    return pd.DataFrame(rows)


BASE = {"매출액": 1000, "매출원가": 600, "판관비": 200, "당기순이익": 50, "매출채권": 100,
        "유동자산": 400, "유형자산": 300, "자산총계": 1000, "부채총계": 500,
        "영업활동현금흐름": 30, "감가상각비": 20}


def test_clean_name_removes_numbering_and_spaces():
    assert _clean_name("Ⅱ. 매출 원가") == "매출원가"
    assert _clean_name("(1) 감가상각비") == "감가상각비"
    assert _clean_name("  2. 감가상각비") == "감가상각비"


def test_extract_items_by_id_and_by_name():
    items = extract_items(fs_rows(BASE, BASE))
    assert items.loc["매출액", "당기"] == 1000            # 계정ID로 찾음
    assert items.loc["판관비", "당기"] == 200             # 계정명으로 찾음
    assert items.loc["감가상각비", "전기"] == 20          # 번호 붙은 계정명도 찾음


def test_depreciation_is_absolute_value():
    cur = dict(BASE, 감가상각비=-20)                       # 현금흐름표에 음수로 적힌 경우
    items = extract_items(fs_rows(cur, cur))
    assert items.loc["감가상각비", "당기"] == 20


def test_unchanged_firm_has_neutral_indices():
    """올해·작년이 같으면 비율 지수는 모두 1, M-Score = 상수 + 계수합 + TATA 기여"""
    r = compute_mscore(extract_items(fs_rows(BASE, BASE)))
    for k in ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]:
        assert r[k] == pytest.approx(1.0)
    tata = (50 - 30) / 1000
    assert r["TATA"] == pytest.approx(tata)
    expected = -4.84 + sum(v for k, v in COEF.items() if k != "TATA") + COEF["TATA"] * tata
    assert r["M-Score"] == pytest.approx(expected)
    assert r["경보"] == (expected > THRESHOLD)
    assert r["중립값 대체"] == "-"


def test_receivables_jump_raises_dsri_and_mscore():
    """매출채권이 매출보다 빨리 늘면(DSRI↑) M-Score가 올라간다"""
    base = compute_mscore(extract_items(fs_rows(BASE, BASE)))
    cur = dict(BASE, 매출채권=300)
    r = compute_mscore(extract_items(fs_rows(cur, BASE)))
    assert r["DSRI"] == pytest.approx(3.0)
    assert r["M-Score"] > base["M-Score"]


def test_missing_account_uses_neutral_value_and_is_recorded():
    cur = {k: v for k, v in BASE.items() if k != "감가상각비"}
    r = compute_mscore(extract_items(fs_rows(cur, cur)))
    assert r["DEPI"] == NEUTRAL["DEPI"]
    assert "DEPI" in r["중립값 대체"]


def test_zero_denominator_does_not_crash():
    cur = dict(BASE, 매출액=0)
    r = compute_mscore(extract_items(fs_rows(cur, BASE)))
    assert math.isfinite(r["M-Score"])
