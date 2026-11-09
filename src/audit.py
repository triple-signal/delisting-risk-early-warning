"""감사 정보(신호 ③)와 감사보고서 강조사항 텍스트(신호 ② 일부) 수집·변수 계산
research_design.md 5·6절. DART 정기보고서 주요정보 API 사용. 임근영 담당"""
import json
import re
import time

import numpy as np
import pandas as pd
import requests

from src.dart import API_KEY, BASE, DATA_DIR

CACHE_DIR = DATA_DIR / "dart_audit"
ENDPOINTS = {
    "opinion": "accnutAdtorNmNdAdtOpinion",   # 감사인 명칭, 감사의견, 강조사항, 핵심감사사항
    "service": "adtServcCnclsSttus",          # 감사용역 체결현황 (보수·시간: 계약/실제)
}

# 강조사항 유형 분류 규칙 (띄어쓰기 제거 후 검색). [구현] 언어모형 분류 전 임시 규칙
EMPHASIS_RULES = {    # 계속기업은 T1으로 따로 계산
    "강조_상폐절차": r"매매거래(가)?정지|거래정지|상장폐지|상장적격성|실질심사|개선기간",
    "강조_소송": r"소송|우발부채",
    "강조_특수관계자": r"특수관계",
}
UNITS = [("억원", 1e8), ("백만원", 1e6), ("천원", 1e3)]


def _fetch(kind, corp_code, year):
    """API 원본(list)을 data/dart_audit/에 저장해 두고 재사용. 자료 없으면 []"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{kind}_{corp_code}_{year}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(f"{BASE}/{ENDPOINTS[kind]}.json",
                     params={"crtfc_key": API_KEY, "corp_code": corp_code,
                             "bsns_year": str(year), "reprt_code": "11011"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d["status"] not in ("000", "013"):
        raise RuntimeError(f"DART 오류 {d['status']}: {d['message']}")
    rows = d.get("list", []) if d["status"] == "000" else []
    time.sleep(0.2)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def _split_periods(rows):
    """행을 당기·전기로 나눈다. 기수(제N기)가 가장 큰 행 = 당기, 그 다음 = 전기.
    기수가 없으면 연도(YYYY년), 그것도 없으면 '당기'/'전기' 글자로 판단"""
    def key(r):
        label = str(r.get("bsns_year", ""))
        m = re.search(r"제\s*(\d+)\s*기", label) or re.search(r"(\d{4})\s*년", label)
        return int(m.group(1)) if m else None

    keys = [key(r) for r in rows]
    if all(k is not None for k in keys) and keys:
        order = sorted(set(keys), reverse=True)
        cur = [r for r, k in zip(rows, keys) if k == order[0]]
        prev = [r for r, k in zip(rows, keys) if len(order) > 1 and k == order[1]]
        return cur, prev
    label = lambda r: re.sub(r"\s", "", str(r.get("bsns_year", "")))
    cur = [r for r in rows if "당기" in label(r)]
    prev = [r for r in rows if "전기" in label(r) and "전전기" not in label(r)]
    return cur, prev


def _amount(cell):
    """칸 안의 숫자를 모두 더한다. 금액 단위(억원·백만원·천원)가 있으면 원으로 환산"""
    s = str(cell)
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", s)]
    if not nums:
        return np.nan
    unit = next((u for name, u in UNITS if name in s), 1)
    return sum(nums) * unit


def _sum(rows, cols, fee=False):
    """여러 행의 값을 더한다. cols는 우선순위 순서(앞 열이 비면 다음 열 사용: 신형식 → 구형식).
    fee=True이면 단위 표시가 없는 금액의 단위를 크기로 추정해 원으로 맞춘다 ([구현])"""
    total = []
    for r in rows:
        for col in cols:
            cell = r.get(col)
            v = _amount(cell)
            if pd.notna(v):
                if fee and not any(name in str(cell) for name, _ in UNITS) and "원" not in str(cell):
                    v = v * (1e6 if v < 1e4 else 1e3 if v < 1e7 else 1)
                total.append(v)
                break
    return sum(total) if total else np.nan


def _opinion(text):
    """감사의견 표기 정리: 적정 / 한정 / 부적정 / 의견거절"""
    s = re.sub(r"\s", "", str(text))
    for label, pat in [("의견거절", r"거절"), ("부적정", r"부적정"), ("한정", r"한정"), ("적정", r"적정")]:
        if re.search(pat, s):
            return label
    return np.nan


def _auditor(name):
    """감사인 이름 정리: 띄어쓰기·'회계법인'·'(주)'·'주식회사' 제거"""
    return re.sub(r"\s|회계법인|\(주\)|주식회사|\(유\)|유한", "", str(name))


def audit_vars(corp_code, year):
    """한 기업·한 사업연도의 감사·강조사항 변수. 당해 사업보고서 하나에서 당기·전기를 함께 읽는다"""
    cur_op, prev_op = _split_periods(_fetch("opinion", corp_code, year))
    cur_sv, prev_sv = _split_periods(_fetch("service", corp_code, year))
    cur = cur_op[0] if cur_op else {}
    prev = prev_op[0] if prev_op else {}

    opinion = _opinion(cur.get("adt_opinion")) if cur else np.nan
    emph = re.sub(r"\s", "", str(cur.get("emphs_matter", "")))
    out = {
        "감사인": cur.get("adtor", np.nan),
        "감사의견": opinion,
        "비적정": float(opinion != "적정") if pd.notna(opinion) else np.nan,
        # A1 감사인 교체
        "A1_감사인교체": (float(_auditor(cur.get("adtor")) != _auditor(prev.get("adtor")))
                     if cur.get("adtor") and prev.get("adtor") else np.nan),
        # T1 계속기업 관련 중요한 불확실성
        "T1_계속기업불확실성": float("계속기업" in emph and "불확실성" in emph) if cur else np.nan,
    }
    for name, pat in EMPHASIS_RULES.items():  # T2 강조사항 유형
        out["T2_" + name] = float(bool(re.search(pat, emph))) if cur else np.nan

    # 감사보수(원)·감사시간: 실제 수행 기준
    fee_cols = ["real_exc_dtls_mendng", "mendng"]     # 실제 보수 → (2019 이전 형식) 보수
    hr_cols = ["real_exc_dtls_time", "tot_reqre_time"]  # 실제 시간 → (2019 이전 형식) 총소요시간
    fee_c, fee_p = _sum(cur_sv, fee_cols, fee=True), _sum(prev_sv, fee_cols, fee=True)
    hr_c, hr_p = _sum(cur_sv, hr_cols), _sum(prev_sv, hr_cols)
    hr_plan = _sum(cur_sv, ["adt_cntrct_dtls_time"])

    def log_change(a, b):
        return np.log(a / b) if pd.notna(a) and pd.notna(b) and a > 0 and b > 0 else np.nan

    out.update({
        "감사보수": fee_c, "감사시간": hr_c,
        "A2_감사시간변화": log_change(hr_c, hr_p),
        "A4_감사보수변화": log_change(fee_c, fee_p),
        "A5_시간초과율": hr_c / hr_plan - 1 if pd.notna(hr_plan) and hr_plan > 0 else np.nan,
    })
    # 이미 상장폐지 사유가 드러난 기업-연도 (사건 시점 ②안: 표시 후 제외 분석)
    out["사유 발생 후"] = float(out["비적정"] == 1 or out["T2_강조_상폐절차"] == 1) if cur else np.nan
    return pd.Series(out)
