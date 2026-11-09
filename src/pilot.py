"""파일럿 (research_design.md 8절): 사건 기업의 사건 직전 2개 회계연도 M-Score·발생액"""
import time

import numpy as np
import pandas as pd

from src.dart import DATA_DIR, get_corp_codes, get_financials
from src.labels import load_delisted
from src.mscore import compute_mscore, extract_items

CACHE_DIR = DATA_DIR / "dart_fs"

# [가정] 2026-11-09 파일럿 1차 테스트용. 팀 확인 필요
PILOT_YEARS = range(2021, 2026)          # 폐지일자 연도 2021~2025
QUOTA = {                                # 폐지 사유별 추출 수 (합 8개)
    "부실:감사의견": 3,
    "부실:실질심사": 3,
    "부실:부도·파산": 1,
    "부실:보고서미제출": 1,
}
SEED = 42
LOOKBACK = 3          # 폐지 연도 직전 몇 개 사업연도까지 거슬러 찾을지
FIRST_YEAR = 2018     # 재무제표 기간 시작 (research_design.md 2절)


def load_financials(corp_code, year):
    """재무제표를 data/dart_fs/에 저장해 두고 재사용. 없으면 빈 표"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{corp_code}_{year}.csv"
    if path.exists():
        if path.stat().st_size <= 5:  # 재무제표 없음으로 저장된 빈 파일
            return pd.DataFrame()
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    fs = get_financials(corp_code, year)
    time.sleep(0.3)  # DART 호출 간격
    fs.to_csv(path, index=False, encoding="utf-8-sig")  # 빈 표도 저장 (재조회 방지)
    return fs


def filing_date(fs):
    """접수번호(rcept_no) 앞 8자리 = 공시 접수일"""
    return pd.to_datetime(str(fs["rcept_no"].iloc[0])[:8], format="%Y%m%d")


def event_years(corp_code, delist_date):
    """사건 직전 2개 회계연도: 폐지일 이전에 공시된 사업보고서 중 가장 최근 2개.
    폐지 연도 직전 LOOKBACK개 사업연도 안에서 찾는다. 반환: (사업연도 목록(오래된 순), 탈락 사유 dict)"""
    found, skipped = [], {}
    for y in range(delist_date.year - 1, delist_date.year - 1 - LOOKBACK, -1):
        if y < FIRST_YEAR or len(found) == 2:
            break
        fs = load_financials(corp_code, y)
        if fs.empty:
            skipped[y] = "재무제표 없음"
        elif filing_date(fs) >= delist_date:
            skipped[y] = f"폐지 후 공시({filing_date(fs).date()})"
        else:
            found.append(y)
    return sorted(found), skipped


def firm_year(corp_code, year):
    """한 기업·한 연도의 M-Score와 발생액. 재무제표가 없으면 None"""
    fs = load_financials(corp_code, year)
    if fs.empty:
        return None
    items = extract_items(fs)
    res = compute_mscore(items)
    c = items["당기"]
    accrual = (c["당기순이익"] - c["영업활동현금흐름"]) / c["자산총계"] if c["자산총계"] else np.nan
    res["발생액"] = accrual
    res["연결/별도"] = "연결" if fs["fs_div"].iloc[0] == "CFS" else "별도"
    return res


def pick_events():
    """사유별 할당(QUOTA)만큼 무작위로 고르되, 폐지 전 공시된 사업보고서가 2개 있는 기업만 채택"""
    corps = get_corp_codes()
    corps = corps[corps["stock_code"].fillna("") != ""][["stock_code", "corp_code"]]
    ev = load_delisted()
    ev = ev[ev["사건"] & ev["폐지일자"].dt.year.isin(PILOT_YEARS)]
    ev = ev.merge(corps, left_on="종목코드", right_on="stock_code", how="left")

    picked, dropped = [], []
    for reason, n in QUOTA.items():
        pool = ev[ev["분류"] == reason].sample(frac=1, random_state=SEED)
        count = 0
        for _, r in pool.iterrows():
            if count == n:
                break
            years, skipped = event_years(r["corp_code"], r["폐지일자"])
            if len(years) < 2:
                dropped.append({"회사명": r["회사명"], "분류": reason,
                                "폐지일자": r["폐지일자"].date(), "제외 연도": skipped})
                continue
            picked.append(r)
            count += 1
    return pd.DataFrame(picked).reset_index(drop=True), pd.DataFrame(dropped)


def prior_mismatch(corp_code, year):
    """당해 보고서의 '전기' 자산총계가 전년 보고서의 '당기' 자산총계와 다르면 True (원자료 오류·재작성 의심)"""
    cur, prev = load_financials(corp_code, year), load_financials(corp_code, year - 1)
    if cur.empty or prev.empty:
        return np.nan
    a = extract_items(cur).loc["자산총계", "전기"]
    b = extract_items(prev).loc["자산총계", "당기"]
    if pd.isna(a) or pd.isna(b):
        return np.nan
    return bool(abs(a - b) > 1)


def run_pilot(sample):
    """선정 기업별로 직전 2개 연도 결과를 한 표로 정리. 자료 점검 열을 함께 붙인다"""
    rows = []
    for _, r in sample.iterrows():
        years, skipped = event_years(r["corp_code"], r["폐지일자"])
        for k, y in enumerate(years):
            res = firm_year(r["corp_code"], y)
            filed = filing_date(load_financials(r["corp_code"], y))
            row = {"시장": r["시장"], "회사명": r["회사명"], "분류": r["분류"],
                   "폐지일자": r["폐지일자"].date(), "사업연도": y, "시점": f"t-{2 - k}"}
            row.update(res.to_dict())
            row["공시일"] = filed.date()
            row["건너뛴 연도"] = ", ".join(f"{yy}:{why}" for yy, why in skipped.items()) or "-"
            row["전기 불일치"] = prior_mismatch(r["corp_code"], y)
            rows.append(row)
    return pd.DataFrame(rows)
