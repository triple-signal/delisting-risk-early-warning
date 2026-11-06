"""OpenDART API로 기업 목록과 재무제표를 가져오는 함수 모음"""
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("DART_API_KEY")
BASE = "https://opendart.fss.or.kr/api"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 보고서 코드
REPORT_CODES = {"사업보고서": "11011", "반기": "11012", "1분기": "11013", "3분기": "11014"}


def get_corp_codes(refresh=False):
    """상장사 고유번호 목록. 처음 한 번만 받아서 data/corp_codes.csv에 저장해 두고 재사용"""
    path = DATA_DIR / "corp_codes.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig")

    r = requests.get(f"{BASE}/corpCode.xml", params={"crtfc_key": API_KEY}, timeout=60)
    r.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(r.content)):
        raise RuntimeError(f"DART 응답 오류 (인증키를 확인하세요): {r.text[:200]}")

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = ET.fromstring(z.read("CORPCODE.xml"))
    rows = [{c.tag: (c.text or "").strip() for c in item} for item in root.iter("list")]
    df = pd.DataFrame(rows)
    df = df[df["stock_code"] != ""].reset_index(drop=True)  # 상장사만 남김

    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


def get_financials(corp_code, year, reprt_code="11011"):
    """단일회사 전체 재무제표. 연결(CFS)이 없으면 별도(OFS)로 다시 시도"""
    for fs_div in ("CFS", "OFS"):
        r = requests.get(
            f"{BASE}/fnlttSinglAcntAll.json",
            params={
                "crtfc_key": API_KEY,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": reprt_code,
                "fs_div": fs_div,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] == "000":
            df = pd.DataFrame(data["list"])
            df["fs_div"] = fs_div
            return df
        if data["status"] != "013":  # 013 = 해당 데이터 없음
            raise RuntimeError(f"DART 오류 {data['status']}: {data['message']}")
    return pd.DataFrame()  # 연결·별도 모두 없음
