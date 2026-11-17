# 작업 인수인계 (강태욱용, 2026-11-11 작성 · 2026-11-17 갱신)

임근영이 진행한 작업을 강태욱의 PC와 Claude Code에서 이어서 하기 위한 안내입니다.
**강태욱 담당: KIND 상장폐지 수집·분류(`src/labels.py`), 수집 완료 자료 정리, 기업-연도 패널 구성** (`src/panel.py`). 융합 모형·가설 검증은 임근영 담당입니다.

## 1. 준비물

- GitHub 계정 (`triple-signal` Organization 멤버, 레포 쓰기 권한)
- Claude Code (VS Code 확장) — 본인 Claude 요금제로 사용
- OpenDART 인증키 — **선택**. 수집 자료를 통째로 전달하므로 패널 구성에는 필요 없습니다 (아래 3절 참고)

## 2. 설치 (처음 한 번)

PowerShell 터미널에서 순서대로 실행합니다.

1. Git, Python 3.14, VS Code 설치
2. 레포 받기
   ```
   cd C:\Users\<본인계정>\projects
   git clone https://github.com/triple-signal/delisting-risk-early-warning.git
   cd delisting-risk-early-warning
   ```
3. 커밋 작성자를 본인으로 설정 (GitHub 기록에서 기여가 구분되도록)
   ```
   git config user.name "<본인 GitHub 아이디>"
   git config user.email "<본인 GitHub 이메일>"
   ```
4. 가상환경과 라이브러리
   ```
   py -3.14 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
5. (선택) 추가 수집이 필요할 때만: 프로젝트 폴더에 `.env` 파일을 만들고 한 줄 저장 `DART_API_KEY=본인키`.
   키는 공유하지 않으며, `.env`는 GitHub에 올라가지 않게 설정되어 있습니다

## 3. 수집 자료 받기

### 수집 결과

전체 표본 수집은 임근영 PC에서 진행했고 **11월 18일 완료** 예정입니다 (처음 예상 11월 14일에서 늦어짐).

| 단계 | 대상 | 저장 위치 | 비고 |
|---|---:|---|---|
| 재무제표 | 19,901 기업-연도 | `data/dart_fs/{corp_code}_{연도}.csv` | 2018~2025, 3,016개 기업 |
| 감사의견·감사용역 | 19,901 기업-연도 | `data/dart_audit/{opinion,service}_{corp_code}_{연도}.json` | 기업-연도당 파일 2개 |
| 사업보고서 원문 | 21,975건 | `data/dart_doc/{접수번호}/{접수번호}.xml.gz` | **2017년 포함** (2018년 서술 변화 T3·T4의 전년 비교용) |

- 수집 실패 건이 있으면 `data/collect_failed.csv`에 목록이 남습니다. 패널 구성 전에 확인합니다
- 기준표: `data/filing_index.csv` (기업-연도별 대상 기업, 최초·최종 접수번호, 최초공시일, 정정횟수)

### 전달 방법

- `data` 폴더 압축본(약 5~6GB)을 구글 드라이브로 전달합니다. 프로젝트 폴더에 `data`로 풀면 됩니다
- KIND 원자료(`data/raw/`), 기업개황(`data/company_info.csv`)도 압축본에 포함됩니다
- `data/pilot_control_map.csv`에는 현재 상장 기업 실명이 있어 **팀 내부에서만** 보관합니다
- `collect.lock`, `collect_log.json`, `collect_run.log`는 수집 운영 파일이라 무시해도 됩니다

### API 키가 필요 없는 이유와 추가 수집

- `load_financials()`, `audit_vars()`, `fetch_document()`는 `data/`에 파일이 있으면 그것을 읽고, 없을 때만 API를 부릅니다
- 키 없이 파일이 없는 기업-연도를 읽으면 "DART 오류"로 멈춥니다 (빈 파일로 저장되지 않음). 패널이 전달받은 자료로만 만들어진다는 확인 장치로 쓸 수 있습니다
- **추가 수집이 필요하면 임근영에게 요청합니다** (수집 경로를 한 곳으로 유지). 해당되는 경우:
  - `collect_failed.csv`에 남은 실패 건 재수집
  - 아직 수집 범위에 없는 자료: H3 보조 자료(2026년 반기·분기보고서), 3절 ①안 채택 시 최초 상장폐지 사유 발생일

## 4. Claude Code에서 시작하기

1. VS Code에서 프로젝트 폴더를 열고 Claude Code 창을 엽니다
2. Claude Code는 `CLAUDE.md`(작업 규칙·진행 상황·역할 분담)를 자동으로 읽습니다
3. 첫 요청 예시:
   > CLAUDE.md, docs/research_design.md, docs/HANDOFF.md를 읽고 지금까지 진행 상황과 내 담당 작업(패널 구성)을 요약해줘. 그다음 src/panel.py 설계안을 제안해줘.

## 5. 지켜야 할 규칙 (CLAUDE.md 요약)

- 기준 문서는 `docs/research_design.md`. 연구 설계 결정(표본·라벨·변수·모형·기준값)은 팀과 정한 뒤 이 문서에 먼저 기록
- **다른 사람 담당 모듈은 고치지 않고 import해서 씁니다.** 고쳐야 하면 먼저 담당자에게 말합니다
  - 공동: `src/dart.py`, `src/mscore.py`
  - 강태욱 본인 담당: `src/labels.py`(KIND 상장폐지 분류), `src/panel.py`
  - 임근영: `src/pilot.py`, `src/company.py`, `src/audit.py`, `src/disclosure.py`, `src/standardize.py`, `src/fusion.py`, `src/collect.py`
- 커밋 메시지 앞에 `[강태욱]` 표시, 본인 계정으로 커밋
- `.env`, `data/`는 절대 GitHub에 올리지 않음
- 현재 상장 기업은 실명 대신 식별번호로만 표시 (공개 레포)

## 6. 패널 구성에 쓸 함수 (참고)

| 신호 | 함수 | 입력 |
|---|---|---|
| 사업연도별 대상 기업·최초 공시 접수번호 | `src.collect.load_index()` | `data/filing_index.csv` |
| 재무제표 원자료 | `src.pilot.load_financials(corp_code, 연도)` | `data/dart_fs/` |
| M-Score·발생액 | `src.mscore.extract_items()`, `compute_mscore()` | 재무제표 원자료 |
| 감사 신호 A1~A5, T1·T2 | `src.audit.audit_vars(corp_code, 연도)` | `data/dart_audit/` |
| 텍스트 신호 T3~T5 | `src.disclosure.text_vars(접수번호, 전년 접수번호)` | `data/dart_doc/` |
| 상장폐지 라벨 | `src.labels.load_delisted()` | `data/raw/` |
| 표준화 | `src.standardize.standardize()` | 패널 |

패널은 `standardize()`에 바로 넣을 수 있는 형태로 만들어 임근영(융합 모형)에게 넘깁니다.
사건 시점·"사유 발생 후" 표시, 미래 정보 누출 방지 원칙은 `docs/research_design.md` 3절·7절을 따릅니다.

## 7. 패널 구성 시 주의할 점

1. **기준 키는 `corp_code` × `사업연도`**, 기준표는 `data/filing_index.csv`
   - `사업연도`는 실수(2017.0)로 저장되어 있으므로 정수로 변환
   - `corp_code`, `stock_code`는 앞자리 0이 있으므로 `dtype=str`로 읽기
2. **최초 공시 기준**: 원문·공시일은 `최초_rcept_no`·`최초공시일` 사용 (기업-연도의 약 24%가 정정공시 있음). 재무제표 API 값은 정정 반영 최신값이라는 한계는 research_design 2절에 기록됨
3. **텍스트 신호**는 `text_vars(당해 접수번호, 전년 접수번호)`. 2018년의 전년은 2017년 원문. 원문은 `.xml.gz`로 압축되어 있지만 `disclosure` 함수가 그대로 읽음
4. **재무제표 빈 파일 = 자료 없음** (수집 실패 아님). 0으로 채우지 말고 결측으로 둠. 결측 표시 열은 `standardize()`가 만듦
5. **미래 정보 누출 방지**: 사건 기업은 상장폐지일 이후 공시된 사업보고서를 입력으로 쓰지 않음 (`최초공시일 < 폐지일`)
6. **"사유 발생 후" 표시 열 필수**: 비적정 감사의견, 강조사항 T2 상폐절차, XI장 T5 거래정지·상폐 절차가 이미 드러난 기업-연도에 표시. 이를 뺀 분석을 함께 제시 (research_design 3절)
7. **라벨**: `load_delisted()` 사건 156건. **보류 21건**(시가총액 미달 4, 해산 17)은 `[미정]`이므로 버리지 말고 별도 표시 열로 남김
8. **미정 항목은 양쪽 모두 가능하게 둠** `[가정]` 팀 확인 필요
   - 예측 기간: 1년 라벨과 2년 라벨을 둘 다 생성
   - 금융업(업종코드 64~66, `data/company_info.csv`): 제외하지 말고 표시 열만 추가
9. **자료 품질 열을 함께 가져옴**: 연결/별도 구분, M-Score 중립값 대체 여부(DEPI 대부분 대체), DART "전기 불일치". 감사시간 입력 오류는 표준화의 1% 윈저화로 처리하므로 패널에는 원값 유지

## 8. 팀 결정 대기 (`[미정]`, research_design 하단 목록)

- 예측 기간(1년/2년), 학습·검증 연도 범위
- 보류 21건 포함 여부, 폐지 사유 선별 기준 확정
- 금융업 처리 방법, 연결/별도 혼용 허용 여부, 포함할 제재 범위
- AQI 단순화와 결측 중립값 처리 승인
