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


def get_company_info(corp_codes, refresh=False):
    """기업개황(시장구분 corp_cls, 업종코드 induty_code, 결산월 acc_mt).
    data/company_info.csv에 쌓아 두고, 아직 없는 기업만 새로 조회한다.
    corp_cls: Y=유가증권, K=코스닥, N=코넥스, E=기타(상장폐지 등)"""
    import time

    path = DATA_DIR / "company_info.csv"
    cols = ["corp_code", "corp_name", "stock_code", "corp_cls", "induty_code", "acc_mt"]
    have = (pd.read_csv(path, dtype=str, encoding="utf-8-sig")
            if path.exists() and not refresh else pd.DataFrame(columns=cols))
    todo = [c for c in corp_codes if c not in set(have["corp_code"])]

    rows = []
    for i, cc in enumerate(todo, 1):
        r = requests.get(f"{BASE}/company.json",
                         params={"crtfc_key": API_KEY, "corp_code": cc}, timeout=30)
        r.raise_for_status()
        d = r.json()
        if d.get("status") == "000":
            rows.append({k: d.get(k, "") for k in cols})
        elif d.get("status") != "013":
            raise RuntimeError(f"DART 오류 {d.get('status')}: {d.get('message')}")
        time.sleep(0.1)
        if i % 200 == 0 or i == len(todo):  # 중간 저장 (끊겨도 이어서 받기)
            have = pd.concat([have, pd.DataFrame(rows, columns=cols)], ignore_index=True)
            rows = []
            have.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"기업개황 {i}/{len(todo)}")
    return have


def get_total_assets(corp_codes, year, reprt_code="11011"):
    """여러 회사의 자산총계(당기)를 100개씩 묶어 조회 (다중회사 주요계정 API).
    연결이 있으면 연결, 없으면 별도. 반환: corp_code → 자산총계"""
    out = {}
    codes = list(corp_codes)
    for i in range(0, len(codes), 100):
        r = requests.get(f"{BASE}/fnlttMultiAcnt.json",
                         params={"crtfc_key": API_KEY, "corp_code": ",".join(codes[i:i + 100]),
                                 "bsns_year": str(year), "reprt_code": reprt_code}, timeout=60)
        r.raise_for_status()
        d = r.json()
        if d["status"] == "013":
            continue
        if d["status"] != "000":
            raise RuntimeError(f"DART 오류 {d['status']}: {d['message']}")
        df = pd.DataFrame(d["list"])
        df = df[df["account_nm"].str.replace(" ", "") == "자산총계"]
        df["amt"] = pd.to_numeric(df["thstrm_amount"].str.replace(",", ""), errors="coerce")
        for cc, g in df.groupby("corp_code"):
            pick = g[g["fs_div"] == "CFS"] if (g["fs_div"] == "CFS").any() else g[g["fs_div"] == "OFS"]
            out[cc] = pick["amt"].iloc[0]
    return pd.Series(out, name="자산총계", dtype=float)
