"""텍스트 신호: 사업보고서 원문에서 MD&A 추출(T3·T4)과 XI장 제재·소송 추출(T5)"""
import gzip

import pytest

from src.disclosure import (_mentioned, load_xml, mdna, mdna_omitted, sanction_litigation, section,
                            text_change)

MDNA = ("1. 예측정보에 대한 주의사항&cr;이 보고서에는 미래에 대한 예측정보가 포함되어 있습니다.&cr;"
        "2. 개요&cr;당사는 올해 매출이 크게 증가하였습니다. 원가 절감으로 영업이익도 개선되었습니다.")
XI = ("1. 우발부채 등&cr;서울중앙지방법원 2023가합12345 손해배상 소송이 진행 중입니다.&cr;"
      "2. 제재 등&cr;불성실공시법인 지정(벌점: 5점)을 받았습니다. 횡령·배임 해당사항 없음.&cr;"
      "당사 주권은 2024년 매매거래정지 상태입니다.")


def report(mdna_body=MDNA, xi_body=XI):
    return (f"<DOCUMENT><SECTION-1><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>{mdna_body}</SECTION-1>"
            f"<SECTION-1><TITLE>XI. 그 밖에 투자자 보호를 위하여 필요한 사항</TITLE>{xi_body}</SECTION-1></DOCUMENT>")


def test_section_found_by_title_ignoring_spaces():
    assert "매출이 크게" in section(report(), r"이사의경영진단")
    assert section(report(), r"없는제목") is None


def test_mdna_drops_forward_looking_disclaimer():
    text = mdna(report())
    assert text.startswith("2. 개요")
    assert "예측정보" not in text


def test_mdna_omitted_is_none():
    xml = report(mdna_body="기업공시서식 작성기준에 따라 분기·반기보고서에는 기재를 생략합니다.")
    assert mdna_omitted(xml)
    assert mdna(xml) is None


def test_mentioned_ignores_negation():
    assert _mentioned("소송이진행중입니다", r"소송")
    assert not _mentioned("소송해당사항없음", r"소송")


def test_sanction_litigation_extracts_facts():
    r = sanction_litigation(report())
    assert r["T5_XI장있음"] == 1.0
    assert r["T5_소송건수"] == 1.0
    assert r["T5_불성실공시건수"] == 1.0
    assert r["T5_벌점합계"] == 5.0
    assert r["T5_횡령배임"] == 0.0          # "해당사항 없음"은 기재로 보지 않음
    assert r["T5_상폐절차기재"] == 1.0


def test_no_section_xi():
    assert sanction_litigation("<DOCUMENT></DOCUMENT>") == {"T5_XI장있음": 0.0}


def test_text_change_identical_vs_rewritten():
    a = "당사는 올해 매출이 크게 증가하였습니다. 원가 절감으로 영업이익도 개선되었습니다."
    b = "회사는 신규 사업에 진출하였고 차입금 상환 일정을 조정하였습니다. 유동성 위험이 커졌습니다."
    same = text_change(a, a)
    assert same["T3_서술변화"] == pytest.approx(0.0, abs=1e-9)
    assert same["T4_삭제비율"] == 0.0
    diff = text_change(a, b)
    assert diff["T3_서술변화"] > 0.3
    assert diff["T4_삭제비율"] == 1.0


def test_text_change_missing_prior_year():
    r = text_change(None, "본문")
    assert all(v != v for v in r.values())      # 모두 NaN


def test_load_xml_handles_gzip_and_euc_kr(tmp_path):
    body = "<DOCUMENT>한글 본문</DOCUMENT>"
    p = tmp_path / "doc.xml.gz"
    p.write_bytes(gzip.compress(body.encode("cp949")))   # 헤더와 달리 EUC-KR로 저장된 경우
    assert load_xml(p) == body
