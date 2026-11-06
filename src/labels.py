"""KIND 상장폐지현황 파일을 읽어 폐지 사유를 분류한다 (research_design.md 3절)"""
import io
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
FILES = {"유가증권": "kind_delisted_kospi.xls", "코스닥": "kind_delisted_kosdaq.xls"}

# 위에서부터 순서대로 검사해 처음 맞는 분류를 쓴다 (띄어쓰기 제거 후 비교)
RULES = [
    ("부실:감사의견", r"감사의견|감사범위"),
    ("부실:실질심사", r"계속성|투명성"),
    ("부실:부도·파산", r"부도|거래정지|파산"),
    ("부실:보고서미제출", r"보고서.*(미제출|제출하지)"),
    ("부실:재무요건", r"자본잠식|매출액"),
    ("보류:시장요건", r"시가총액|분산요건"),           # 팀 결정 대기
    ("보류:해산", r"해산"),                         # 팀 결정 대기 (대부분 합병 해산 추정)
    ("제외:비부실", r"합병|완전자회사|이전상장|유가증권시장상장|신청|존속기간|예비심사"),
]


def _read_kind(path):
    """KIND 엑셀은 실제로는 EUC-KR 인코딩의 HTML 표다"""
    html = Path(path).read_bytes().decode("euc-kr", errors="replace")
    return pd.read_html(io.StringIO(html), converters={"종목코드": str})[0]


def classify(reason, company):
    if re.search(r"스팩|기업인수목적", str(company)):
        return "제외:스팩"
    s = re.sub(r"\s", "", str(reason))
    for label, pattern in RULES:
        if re.search(pattern, s):
            return label
    return "미분류"


def load_delisted():
    """두 시장 파일을 합치고 분류 열을 붙인다"""
    frames = []
    for market, fname in FILES.items():
        df = _read_kind(RAW_DIR / fname)
        df["시장"] = market
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["종목코드"] = df["종목코드"].str.zfill(6)
    df["폐지일자"] = pd.to_datetime(df["폐지일자"])
    df["분류"] = [classify(r, c) for r, c in zip(df["폐지사유"], df["회사명"])]
    df["사건"] = df["분류"].str.startswith("부실")
    return df[["시장", "회사명", "종목코드", "폐지일자", "폐지사유", "분류", "사건"]]
