# 프로젝트 안내 (Claude Code용)

한국회계학회 제6회 대학생 회계경진대회(세션 2: AI 활용 회계분석) 출품 연구의 분석 코드 레포다.
팀 트리플 시그널(숭실대). 주제: 숫자·텍스트·감사 신호를 융합한 상장폐지 회피 위험 조기경보 모형.
대회 종료 후 팀원 동의를 받아 공개 레포로 전환했고(2026-11-10), 포트폴리오로 계속 개발한다.
이 파일은 AI 코딩 도구(Claude Code)가 작업할 때 읽는 안내서다.

## 가장 중요한 규칙

1. **`docs/research_design.md`가 기준 문서다.** 표본, 기간, 시장, 지표, 임계값 등은 이 문서를 그대로 따른다.
2. **문서에 없는 값을 임의로 정하지 않는다.** 정해야 할 값이 생기면 먼저 묻는다.
   진행 편의상 임시로 정해야 하면 답변에 **[가정]**이라고 표시하고 이유를 적는다.
3. `[미정]` 항목은 팀 결정 전까지 사용하지 않는다. 결정되면 research_design.md를 먼저 고치고 코드에 반영한다.
4. 코드를 짜면서 새로 정한 내용은 research_design.md에 `[구현]`(팀 확인 필요)으로 기록한다.

## 작업 안내 방식

- 연구 설계와 회계·감사 판단은 팀(공인회계사 시험 합격자 포함)이 하고, AI는 구현과 자료 점검을 맡는다.
- 답변은 한국어로, 단계를 번호로 나눠 하나씩 안내한다. 명령어는 어디(터미널/편집창/노트북)에서 실행하는지 밝힌다.
- 코드를 고칠 때는 일부 줄만 고치라고 하지 말고 **함수 단위로 통째로** 바꾼다 (들여쓰기 실수 방지).
- 회계 개념과 연결해서 설명하면 이해가 빠르다.

## 환경

- Windows, PowerShell, VS Code
- 경로: `C:\Users\tomvv\projects\delisting-risk-early-warning`
- Python 3.14 가상환경 `.venv` (`py -3.14 -m venv .venv` → `.venv\Scripts\activate`)
- 라이브러리: pandas, matplotlib, openpyxl, ipykernel, requests, python-dotenv (`requirements.txt`)
- 노트북 커널은 `.venv` 선택. 노트북은 `notebooks/` 안에서 `sys.path.insert(0, "..")` 후 `from src... import`
- `src` 파일을 고치면 노트북 Restart 필요
- GitHub: Organization `triple-signal` / 레포 `delisting-risk-early-warning` (Public, 2026-11-10 전환)

## 절대 GitHub에 올리면 안 되는 것

- `.env` (DART_API_KEY). 인증키를 코드·노트북·답변에 직접 쓰지 않는다
- `data/` (원자료·수집 데이터), `.venv/`
- 커밋 전에 변경 목록에 `.env`, `data/`가 없는지 확인하도록 안내한다

## 레포 구조

```
docs/research_design.md   연구 설계 기준 문서
src/dart.py               OpenDART API: get_corp_codes(), get_financials(), get_company_info(), get_total_assets()
src/mscore.py             Beneish M-Score 8변수: extract_items(), compute_mscore()
src/labels.py             KIND 상장폐지 사유 분류: load_delisted()
src/pilot.py              파일럿: pick_events(), run_pilot(), match_controls(), run_controls(), compare()
notebooks/01_collect_test.ipynb   수집 테스트
notebooks/02_mscore_test.ipynb    M-Score 계산 테스트 (대형 상장사 1곳)
notebooks/03_pilot_mscore.ipynb   파일럿: 사건 8개 + 대조군 8개 M-Score 비교
data/corp_codes.csv       DART 전체 기업 목록 119,949개 (상장폐지 기업 포함)
data/company_info.csv     기업개황 4,013개 (시장구분·업종코드·결산월, 2026-11-09 수집)
data/dart_fs/             재무제표 캐시 ({corp_code}_{연도}.csv, 빈 파일 = 자료 없음)
data/pilot_control_map.csv  대조군 ID ↔ 실명 대응표 (현재 상장 기업, 절대 공개 금지)
data/raw/kind_delisted_kospi.xls   KIND 상장폐지현황 유가증권 (2018-01-01~2026-11-06)
data/raw/kind_delisted_kosdaq.xls  KIND 상장폐지현황 코스닥 (같은 기간)
```

KIND 엑셀은 실제로는 EUC-KR 인코딩 HTML 표다 (`labels.py`의 `_read_kind` 참고).

## 진행 상황 (2026-11-09 기준)

완료
- 개발 환경, GitHub 팀 레포, DART 인증키
- 재무제표 수집 함수 (연결 우선, 없으면 별도)
- M-Score 계산 모듈. 대형 상장사 1곳으로 동작 확인 (감가상각비가 주석에만 있으면 DEPI 중립값 대체됨)
- 상장폐지 라벨 분류: 431건 중 사건 156건 (유가증권 22, 코스닥 134), 보류 21건
- 파일럿 (research_design.md 8절, 2026-11-09)
  - 사건 기업 8개: 폐지 2021~2025년, 사유별 무작위(시드 42) `[가정]`
  - "직전 2개 회계연도" = 폐지일 이전 공시된 최근 2개 사업보고서 `[결정]`
  - 대조군: 같은 시장 · 업종코드 앞 2자리 · t-2 자산총계 최근접 1:1 `[결정]`. 결과에는 ID(C01~)만 표시
  - 결과: 경보 비율 사건군 6/8(75%), 대조군 1/8(12.5%)

팀 결정 대기 (`[미정]`)
- 시가총액 미달 4건(일정실업, 수성웹툰, 원풍물산, 코이즈)을 사건에 포함할지
- 파산 언급 없는 "해산 사유 발생" 17건(유가증권)을 제외할지. 대부분 합병 해산으로 추정되나 개별 확인 전
- 대조군 규모 차이 허용 한도 (애닉 짝 6.6배)
- 골든센츄리(업종 64992 비금융 지주회사)를 금융업으로 따로 처리할지
- "발생액 상위" 기준, M-Score 극단값 처리(절단·윈저화)
- 그 밖의 미정 항목은 research_design.md 하단 목록 참고

알려진 자료 문제
- DEPI 중립값 대체가 대부분 (감가상각비 계정 미검출) → extract_items 탐색 규칙 개선 여지
- DART가 정정보고서 접수번호를 주면 공시일이 늦게 잡힘
- DART 원자료 오류 사례 있음 (에스제이케이 2020 = 2019 숫자). "전기 불일치" 열로 점검

다음 단계
1. 위 팀 결정 반영
2. 파일럿 확대 또는 전체 사건 156건으로 M-Score 산출 (범위는 먼저 묻는다)
3. 이후 텍스트·감사 신호 추가, 융합 모형

## 작업 방식

- "올려"는 변경 파일만 골라 커밋 후 `main`에 바로 push하는 것을 뜻한다 (브랜치·PR 사용 안 함)
- `.vscode/`, `회계경진대회/` 폴더는 커밋하지 않는다

## 참고

- 유가증권 사건이 22건으로 적어 시장별 결과는 불안정할 수 있다. 코스피 결과의 제시 방식은 팀 판단 사항
- 기업 실명은 상장폐지·제재 확정 사례로 한정하고, 현재 상장 기업의 위험 점수는 익명·식별번호로 처리한다
