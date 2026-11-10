"""사업보고서 원문 텍스트 신호 (research_design.md 5절 T3·T4·T5). 임근영 담당

- T3 서술 변화량: IV. 이사의 경영진단 및 분석의견(MD&A)의 올해·작년 유사도로 측정 (1 − 코사인 유사도)
- T4 위험 서술 축소: 작년 MD&A 문장 중 올해 비슷한 문장이 없는 비율, 분량 증감률
- T5 제재·소송: XI. 그 밖에 투자자 보호… 의 '우발부채 등', '제재 등' 항목에서 사실 정보 추출
유사도는 우선 글자 2~3개 조각(n-gram) 빈도의 코사인 유사도로 계산한다 ([구현] 비교 기준. 임베딩 모델은 추후 추가)
"""
import gzip
import io
import re
import time
import zipfile

import numpy as np
import pandas as pd
import requests
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.dart import API_KEY, BASE, DATA_DIR

DOC_DIR = DATA_DIR / "dart_doc"
SIM_DELETED = 0.5   # [구현] 작년 문장의 올해 최대 유사도가 이 값 미만이면 '삭제된 서술'로 본다
PROCEDURE = r"매매거래(가)?정지|거래정지|상장폐지|상장적격성|실질심사|개선기간"   # audit.py와 같은 기준
CASE_NO = r"\d{4}\s*(가합|가단|가소|나|다|하합|하단|회합|회단|고합|고단|노|카합|카단|구합|구단)\s*\d+"


# ---------------- 원문 수집·읽기 ----------------
def fetch_document(rcept_no):
    """사업보고서 본문 XML을 data/dart_doc/{접수번호}/{접수번호}.xml.gz로 압축 저장하고 경로 반환.
    감사보고서 첨부는 저장하지 않는다. 예전에 압축 없이 받은 .xml이 있으면 그것을 쓴다"""
    d = DOC_DIR / str(rcept_no)
    for path in (d / f"{rcept_no}.xml", d / f"{rcept_no}.xml.gz"):
        if path.exists():
            return path
    r = requests.get(f"{BASE}/document.xml", params={"crtfc_key": API_KEY, "rcept_no": rcept_no}, timeout=120)
    r.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(r.content)):
        raise RuntimeError(f"원문 수집 오류 {rcept_no}: {r.text[:150]}")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = f"{rcept_no}.xml"
        if name not in z.namelist():   # 본문 파일 이름이 다른 경우: 첨부(_숫자)가 아닌 첫 xml
            name = next(n for n in z.namelist() if n.endswith(".xml") and "_" not in n)
        d.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(z.read(name)))
    time.sleep(0.5)
    return path


def load_xml(path):
    """압축(.gz) 여부를 자동 판단. 헤더에 utf-8이라 적혀 있어도 실제로는 EUC-KR인 파일이 있어 둘 다 시도한다"""
    b = path.read_bytes()
    if str(path).endswith(".gz"):
        b = gzip.decompress(b)
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp949", errors="replace")


def _clean(fragment):
    """태그 제거, 줄바꿈 기호(&cr;) 처리, 공백 정리"""
    s = fragment.replace("&cr;", "\n")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&[a-z]+;", " ", s)
    return re.sub(r"[ \t　]+", " ", re.sub(r"\n\s*", "\n", s)).strip()


def section(xml, title_pattern):
    """제목이 title_pattern에 맞는 첫 SECTION의 본문 텍스트. 없으면 None"""
    for m in re.finditer(r"<SECTION-(\d)[^>]*>\s*<TITLE[^>]*>([^<]*)</TITLE>", xml):
        if re.search(title_pattern, re.sub(r"\s", "", m.group(2))):
            end = xml.find(f"</SECTION-{m.group(1)}>", m.end())
            return _clean(xml[m.end():end if end > 0 else len(xml)])
    return None


def mdna_omitted(xml):
    """MD&A 기재를 생략했는지 (기업공시서식 작성기준에 따른 생략 문구만 있는 경우)"""
    text = section(xml, r"이사의경영진단")
    return text is not None and len(text) < 200 and "생략" in text


def mdna(xml):
    """IV. 이사의 경영진단 및 분석의견. 모든 회사에 비슷하게 들어가는 '예측정보에 대한 주의사항' 문단은 뺀다.
    기재를 생략한 경우는 None"""
    text = section(xml, r"이사의경영진단")
    if text is None or mdna_omitted(xml):
        return None
    m = re.search(r"예측정보에\s*대한\s*주의\s*사항", text)
    if m:
        nxt = re.search(r"\n?\s*2\s*\.\s*\S", text[m.end():])   # 다음 번호(2.)부터 본문
        text = text[m.end() + nxt.start():] if nxt else text[m.end():]
    return text.strip()


# ---------------- T3·T4 서술 변화 ----------------
def _sentences(text):
    parts = re.split(r"(?<=다\.)\s+|(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 15]   # 표 조각·번호 같은 짧은 조각 제외


def _vectorize(docs):
    return CountVectorizer(analyzer="char_wb", ngram_range=(2, 3)).fit_transform(docs)


def text_change(prev_text, cur_text):
    """T3 서술 변화량, T4 삭제 비율·분량 증감률"""
    if not prev_text or not cur_text:
        return {"T3_서술변화": np.nan, "T4_삭제비율": np.nan, "T4_분량변화": np.nan}
    v = _vectorize([prev_text, cur_text])
    t3 = 1 - cosine_similarity(v[0], v[1])[0, 0]
    ps, cs = _sentences(prev_text), _sentences(cur_text)
    deleted = np.nan
    if ps and cs:
        vs = _vectorize(ps + cs)
        sim = cosine_similarity(vs[:len(ps)], vs[len(ps):])
        deleted = float((sim.max(axis=1) < SIM_DELETED).mean())
    return {"T3_서술변화": t3, "T4_삭제비율": deleted,
            "T4_분량변화": np.log(len(cur_text) / len(prev_text))}


# ---------------- T5 제재·소송 ----------------
def _mentioned(s, pattern, window=30):
    """pattern이 나오고, 바로 뒤 window 글자 안에 '없' (해당사항 없음 등)이 없는 경우가 한 번이라도 있으면 True"""
    return any("없" not in s[m.end():m.end() + window] for m in re.finditer(pattern, s))


def sanction_litigation(xml):
    """XI. 그 밖에 투자자 보호를 위하여 필요한 사항 전체에서 제재·소송·사고 사실 추출 ([구현] 규칙 기반).
    2020년 이전 보고서는 하위 항목이 제목 없이 본문에 있어, 서식과 무관하게 XI장 전체를 대상으로 한다"""
    xi = section(xml, r"그밖에투자자")
    if xi is None:
        return {"T5_XI장있음": 0.0}
    s = re.sub(r"\s", "", xi)
    penalties = [float(x) for x in re.findall(r"벌점[:：]?(\d+(?:\.\d+)?)점", s)]
    return {
        "T5_XI장있음": 1.0,
        "T5_불성실공시건수": float(s.count("불성실공시")),
        "T5_벌점합계": float(sum(penalties)),
        "T5_소송건수": float(len(set(re.findall(CASE_NO, s)))),
        "T5_소송기재": float(_mentioned(s, r"소송")),
        "T5_횡령배임": float(_mentioned(s, r"횡령|배임")),
        "T5_상폐절차기재": float(bool(re.search(PROCEDURE, s))),
    }


# ---------------- 한 기업·한 연도 ----------------
def text_vars(rcept_no, prev_rcept_no=None):
    """당해 사업보고서(접수번호)의 T3·T4(작년 보고서와 비교)·T5와 장별 분량"""
    xml = load_xml(fetch_document(rcept_no))
    cur = mdna(xml)
    prev = mdna(load_xml(fetch_document(prev_rcept_no))) if prev_rcept_no else None
    out = {"MD&A 분량": len(cur) if cur else np.nan, "MD&A 생략": float(mdna_omitted(xml))}
    out.update(text_change(prev, cur))
    out.update(sanction_litigation(xml))
    return pd.Series(out)
