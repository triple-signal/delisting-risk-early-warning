"""기업개황·다중회사 자산총계 수집 (대조군 매칭용). 임근영 담당
공동 작업 모듈 src/dart.py의 API 설정(API_KEY, BASE, DATA_DIR)을 가져다 쓰고, dart.py 자체는 고치지 않는다"""
import time

import pandas as pd
import requests

from src.dart import API_KEY, BASE, DATA_DIR


def get_company_info(corp_codes, refresh=False):
    """기업개황(시장구분 corp_cls, 업종코드 induty_code, 결산월 acc_mt).
    data/company_info.csv에 쌓아 두고, 아직 없는 기업만 새로 조회한다.
    corp_cls: Y=유가증권, K=코스닥, N=코넥스, E=기타(상장폐지 등)"""
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
