"""전체 표본 수집 (2018~2025 사업연도, 유가증권·코스닥). 임근영 담당

실행 (VS Code 터미널, 프로젝트 폴더에서):
    .venv\\Scripts\\python -m src.collect            # 이어서 수집 (하루 한도까지)
    .venv\\Scripts\\python -m src.collect --status   # 진행 상황만 보기

단계: ① 사업보고서 목록 → ② 재무제표 → ③ 감사의견·감사용역 → ④ 사업보고서 원문
- 이미 받은 자료는 건너뛴다 (언제 멈춰도 다음 실행에서 이어서 받음)
- 하루 호출 수가 DAILY_BUDGET에 닿거나 DART가 '요청 제한 초과(020)'를 주면 멈춘다
- 상장사 기준 `[결정 2026-11-10]`: 해당 연도 사업보고서를 낸 회사 중 종목코드가
  현재 유가증권·코스닥 상장사 또는 KIND 2018년 이후 폐지 목록에 있는 회사
"""
import argparse
import datetime as dt
import json
import re
import sys
import time

import pandas as pd
import requests

from src.audit import _fetch as fetch_audit
from src.dart import API_KEY, BASE, DATA_DIR
from src.disclosure import fetch_document
from src.labels import load_delisted
from src.pilot import load_financials

YEARS = range(2018, 2026)        # 재무·감사 신호 사업연도
DOC_YEARS = range(2017, 2026)    # 원문은 2017년도 받음 (2018년 서술 변화량 비교용)
DAILY_BUDGET = 18000             # [구현] DART 하루 한도(약 2만) 대비 여유
INDEX_PATH = DATA_DIR / "filing_index.csv"
LOG_PATH = DATA_DIR / "collect_log.json"
FAIL_PATH = DATA_DIR / "collect_failed.csv"


# ---------------- 호출 수 세기 ----------------
class Budget:
    """오늘 호출 수를 data/collect_log.json에 기록. requests.get을 감싸 모든 모듈의 호출을 센다"""

    def __init__(self, limit):
        self.limit = limit
        self.log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {}
        self.today = dt.date.today().isoformat()
        self._get = requests.get
        requests.get = self._counting_get

    @property
    def used(self):
        return self.log.get(self.today, 0)

    def _counting_get(self, *args, **kwargs):
        if self.used >= self.limit:
            raise BudgetExhausted()
        self.log[self.today] = self.used + 1
        if self.used % 100 == 0:
            self.save()
        return self._get(*args, **kwargs)

    def save(self):
        LOG_PATH.write_text(json.dumps(self.log, ensure_ascii=False, indent=1), encoding="utf-8")


class BudgetExhausted(Exception):
    pass


def _is_limit_error(e):
    """DART '요청 제한 초과'(상태코드 020)인지. 접수번호(예: 2020…)에 든 020과 헷갈리지 않게 상태코드 형태만 본다"""
    return bool(re.search(r"오류 020\b|\"status\"\s*:\s*\"020\"|<status>020</status>|요청\s*제한|사용\s*한도", str(e)))


# ---------------- ① 사업보고서 목록 ----------------
def _quarters(start, end):
    """검색 기간: 회사 지정 없이 검색하면 3개월까지만 가능해 분기로 나눈다"""
    d = start
    while d <= end:
        q_end = min((pd.Timestamp(d) + pd.offsets.QuarterEnd(0)).date(), end)
        yield d, q_end
        d = q_end + dt.timedelta(days=1)


def build_index():
    """2018-01-01 ~ 오늘 공시된 사업보고서(A001) 전체 목록 → 상장사만 남겨 data/filing_index.csv"""
    rows = []
    for b, e in _quarters(dt.date(2018, 1, 1), dt.date.today()):
        page = 1
        while True:
            d = requests.get(f"{BASE}/list.json", params={
                "crtfc_key": API_KEY, "bgn_de": b.strftime("%Y%m%d"), "end_de": e.strftime("%Y%m%d"),
                "pblntf_detail_ty": "A001", "page_count": 100, "page_no": page}, timeout=60).json()
            if d["status"] == "013":
                break
            if d["status"] != "000":
                raise RuntimeError(f"DART 오류 {d['status']}: {d['message']}")
            rows += d["list"]
            if page >= d["total_page"]:
                break
            page += 1
            time.sleep(0.2)
        print(f"  목록 {b}~{e}: 누적 {len(rows):,}건")
    df = pd.DataFrame(rows)

    # 결산연월 → 사업연도. '[기재정정]사업보고서 (2023.12)' 같은 정정 표기 포함
    period = df["report_nm"].str.extract(r"\((\d{4})\.(\d{2})\)")
    df["사업연도"] = pd.to_numeric(period[0], errors="coerce")
    df["결산월"] = period[1]
    df["정정"] = df["report_nm"].str.startswith("[")

    # 상장사 기준 (모듈 설명 참고)
    info = pd.read_csv(DATA_DIR / "company_info.csv", dtype=str, encoding="utf-8-sig")
    listed = set(info.loc[info["corp_cls"].isin(["Y", "K"]), "stock_code"].dropna())
    listed |= set(load_delisted()["종목코드"])
    df = df[df["stock_code"].fillna("").isin(listed) & df["사업연도"].isin(DOC_YEARS)]

    # 회사·사업연도별 최초 공시와 최종 공시
    df = df.sort_values(["corp_code", "사업연도", "rcept_dt", "rcept_no"])
    g = df.groupby(["corp_code", "사업연도"])
    idx = g.first()[["corp_name", "stock_code", "결산월", "rcept_no", "rcept_dt"]]
    idx = idx.rename(columns={"rcept_no": "최초_rcept_no", "rcept_dt": "최초공시일"})
    idx["최종_rcept_no"] = g["rcept_no"].last()
    idx["정정횟수"] = g["정정"].sum()
    idx = idx.reset_index()
    idx.to_csv(INDEX_PATH, index=False, encoding="utf-8-sig")
    return idx


def load_index():
    idx = pd.read_csv(INDEX_PATH, dtype=str, encoding="utf-8-sig")
    idx["사업연도"] = pd.to_numeric(idx["사업연도"]).astype(int)   # 저장 시 '2017.0' 형태로 기록될 수 있음
    return idx


# ---------------- ②③④ 단계별 수집 ----------------
def _failed():
    return set(pd.read_csv(FAIL_PATH, dtype=str)["key"]) if FAIL_PATH.exists() else set()


def _record_fail(key, err):
    new = pd.DataFrame([{"key": key, "오류": str(err)[:200], "시각": dt.datetime.now().isoformat(timespec="seconds")}])
    new.to_csv(FAIL_PATH, mode="a", header=not FAIL_PATH.exists(), index=False, encoding="utf-8-sig")


def _done(stage, corp, year, rcept):
    if stage == "재무제표":
        return (DATA_DIR / "dart_fs" / f"{corp}_{year}.csv").exists()
    if stage == "감사":
        return all((DATA_DIR / "dart_audit" / f"{k}_{corp}_{year}.json").exists() for k in ("opinion", "service"))
    d = DATA_DIR / "dart_doc" / str(rcept)
    return (d / f"{rcept}.xml").exists() or (d / f"{rcept}.xml.gz").exists()


def tasks(idx):
    """(단계, corp_code, 사업연도, 최초 접수번호) 목록. 단계 순서: 재무제표 → 감사 → 원문"""
    out = []
    for stage, years in (("재무제표", YEARS), ("감사", YEARS), ("원문", DOC_YEARS)):
        sub = idx[idx["사업연도"].isin(years)]
        out += [(stage, r.corp_code, r.사업연도, r.최초_rcept_no) for r in sub.itertuples()]
    return out


def run_task(stage, corp, year, rcept):
    if stage == "재무제표":
        load_financials(corp, year)
    elif stage == "감사":
        fetch_audit("opinion", corp, year)
        fetch_audit("service", corp, year)
    else:
        fetch_document(rcept)   # 최초 공시 원문 (정정 전, 미래 정보 누출 방지)


def status(idx):
    failed = _failed()
    t = pd.DataFrame(tasks(idx), columns=["단계", "corp", "연도", "rcept"])
    t["완료"] = [_done(*x) for x in t[["단계", "corp", "연도", "rcept"]].itertuples(index=False)]
    t["실패"] = [f"{s}|{c}|{y}" in failed for s, c, y in zip(t["단계"], t["corp"], t["연도"])]
    summary = t.groupby("단계", sort=False).agg(전체=("완료", "size"), 완료=("완료", "sum"), 실패=("실패", "sum"))
    summary["남음"] = summary["전체"] - summary["완료"] - summary["실패"]
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="진행 상황만 출력")
    ap.add_argument("--budget", type=int, default=DAILY_BUDGET, help="오늘 최대 호출 수")
    args = ap.parse_args()

    budget = Budget(args.budget)
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M}] 오늘 사용한 호출 수: {budget.used:,} / {budget.limit:,}")
    try:
        if not INDEX_PATH.exists():
            print("① 사업보고서 목록 수집")
            build_index()
        idx = load_index()
        print(f"   대상: 기업 {idx['corp_code'].nunique():,}곳, 기업-연도 {len(idx):,}개")
        if args.status:
            print(status(idx))
            return

        failed = _failed()
        todo = [t for t in tasks(idx) if not _done(*t) and f"{t[0]}|{t[1]}|{t[2]}" not in failed]
        print(f"   남은 작업 {len(todo):,}건")
        for i, (stage, corp, year, rcept) in enumerate(todo, 1):
            try:
                run_task(stage, corp, year, rcept)
            except BudgetExhausted:
                raise
            except requests.exceptions.RequestException as e:   # 일시적 네트워크 문제: 실패로 기록하지 않고 다음 실행 때 다시 시도
                print(f"   네트워크 오류, 10초 후 계속: {str(e)[:80]}")
                time.sleep(10)
            except Exception as e:
                if _is_limit_error(e):
                    print("DART 요청 한도에 도달했습니다.")
                    raise BudgetExhausted()
                _record_fail(f"{stage}|{corp}|{year}", e)
                time.sleep(1)
            if i % 200 == 0:
                print(f"   [{dt.datetime.now():%H:%M}] {stage} 진행 {i:,}/{len(todo):,} (오늘 호출 {budget.used:,})")
        print(status(idx))
        print("\n수집이 모두 끝났습니다. 수집을 위해 바꾼 전원·절전 설정(덮개 닫기 등)이 있다면 원래대로 되돌리세요.")
    except BudgetExhausted:
        print(f"\n오늘 호출 한도({budget.limit:,})에 도달해 멈춥니다. 내일 같은 명령으로 이어서 받으세요.")
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다. 같은 명령으로 이어서 받을 수 있습니다.")
    finally:
        budget.save()


if __name__ == "__main__":
    sys.exit(main())
