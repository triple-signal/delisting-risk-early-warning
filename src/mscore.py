"""Beneish M-Score(8변수 모형) 계산"""
import re

import numpy as np
import pandas as pd

# 항목별 탐색 규칙: (재무제표 구분, IFRS 계정ID 후보, 계정명 후보)
# 계정ID로 먼저 찾고, 없으면 계정명(띄어쓰기 무시)으로 찾는다
RULES = {
    "매출액": (["IS", "CIS"], ["ifrs-full_Revenue"],
            ["매출액", "수익(매출액)", "영업수익", "매출"]),
    "매출원가": (["IS", "CIS"], ["ifrs-full_CostOfSales"], ["매출원가"]),
    "판관비": (["IS", "CIS"], ["dart_TotalSellingGeneralAdministrativeExpenses"],
            ["판매비와관리비", "판매비와일반관리비"]),
    "당기순이익": (["IS", "CIS"], ["ifrs-full_ProfitLoss"],
              ["당기순이익", "당기순이익(손실)", "당기순손실", "당기순손익"]),
    "매출채권": (["BS"], ["ifrs-full_TradeAndOtherCurrentReceivables",
                        "ifrs-full_CurrentTradeReceivables",
                        "dart_ShortTermTradeReceivable"],
             ["매출채권", "매출채권및기타채권", "매출채권및기타유동채권"]),
    "유동자산": (["BS"], ["ifrs-full_CurrentAssets"], ["유동자산"]),
    "유형자산": (["BS"], ["ifrs-full_PropertyPlantAndEquipment"], ["유형자산"]),
    "자산총계": (["BS"], ["ifrs-full_Assets"], ["자산총계"]),
    "부채총계": (["BS"], ["ifrs-full_Liabilities"], ["부채총계"]),
    "영업활동현금흐름": (["CF"], ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
                 ["영업활동현금흐름", "영업활동으로인한현금흐름"]),
    "감가상각비": (["CF"], ["ifrs-full_AdjustmentsForDepreciationExpense",
                        "ifrs-full_DepreciationExpense"],
              ["감가상각비", "유형자산감가상각비"]),
}

# 지수별 계산이 안 될 때 넣는 중립값 (이익조정 신호 없음으로 간주)
NEUTRAL = {"DSRI": 1, "GMI": 1, "AQI": 1, "SGI": 1, "DEPI": 1, "SGAI": 1, "TATA": 0, "LVGI": 1}
COEF = {"DSRI": 0.920, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892,
        "DEPI": 0.115, "SGAI": -0.172, "TATA": 4.679, "LVGI": -0.327}
THRESHOLD = -1.78


def _clean_name(name):
    """계정명 정리: 띄어쓰기, 앞의 번호(Ⅰ. 1. (1) 등) 제거"""
    s = re.sub(r"\s", "", str(name))
    return re.sub(r"^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|\(?\d+\)?)\.?", "", s)


def _to_num(x):
    return pd.to_numeric(str(x).replace(",", ""), errors="coerce")


def extract_items(fs):
    """재무제표(DART 원본)에서 M-Score에 필요한 항목의 당기·전기 금액을 뽑는다"""
    fs = fs.copy()
    fs["_name"] = fs["account_nm"].map(_clean_name)
    rows = {}
    for item, (sj_divs, ids, names) in RULES.items():
        part = fs[fs["sj_div"].isin(sj_divs)]
        hit = part[part["account_id"].isin(ids)]
        if hit.empty:
            hit = part[part["_name"].isin([_clean_name(n) for n in names])]
        if hit.empty and item == "감가상각비":
            hit = part[part["_name"].str.contains("감가상각비", na=False)]
        if hit.empty:
            rows[item] = {"당기": np.nan, "전기": np.nan}
        else:
            r = hit.iloc[0]
            rows[item] = {"당기": _to_num(r["thstrm_amount"]), "전기": _to_num(r["frmtrm_amount"])}
    items = pd.DataFrame(rows).T
    items.loc["감가상각비"] = items.loc["감가상각비"].abs()
    return items


def _div(a, b):
    return a / b if pd.notna(a) and pd.notna(b) and b != 0 else np.nan


def compute_mscore(items):
    """항목표(extract_items 결과)로 8개 지수와 M-Score 계산"""
    c, p = items["당기"], items["전기"]

    def gross_margin(x):
        return _div(x["매출액"] - x["매출원가"], x["매출액"])

    def soft_assets(x):  # 유동자산·유형자산이 아닌 자산의 비중
        return 1 - _div(x["유동자산"] + x["유형자산"], x["자산총계"])

    def dep_rate(x):
        return _div(x["감가상각비"], x["감가상각비"] + x["유형자산"])

    idx = {
        "DSRI": _div(_div(c["매출채권"], c["매출액"]), _div(p["매출채권"], p["매출액"])),
        "GMI": _div(gross_margin(p), gross_margin(c)),
        "AQI": _div(soft_assets(c), soft_assets(p)),
        "SGI": _div(c["매출액"], p["매출액"]),
        "DEPI": _div(dep_rate(p), dep_rate(c)),
        "SGAI": _div(_div(c["판관비"], c["매출액"]), _div(p["판관비"], p["매출액"])),
        "TATA": _div(c["당기순이익"] - c["영업활동현금흐름"], c["자산총계"]),
        "LVGI": _div(_div(c["부채총계"], c["자산총계"]), _div(p["부채총계"], p["자산총계"])),
    }
    missing = [k for k, v in idx.items() if pd.isna(v)]
    idx = {k: (NEUTRAL[k] if pd.isna(v) else v) for k, v in idx.items()}
    m = -4.84 + sum(COEF[k] * v for k, v in idx.items())

    result = pd.Series(idx)
    result["M-Score"] = m
    result["경보"] = m > THRESHOLD
    result["중립값 대체"] = ", ".join(missing) if missing else "-"
    return result