# 작업 인수인계 (강태욱용, 2026-11-11)

임근영이 진행한 작업을 강태욱의 PC와 Claude Code에서 이어서 하기 위한 안내입니다.
**강태욱 담당: 수집 완료 자료 정리, 기업-연도 패널 구성** (`src/panel.py`). 융합 모형·가설 검증은 임근영 담당입니다.

## 1. 준비물

- GitHub 계정 (`triple-signal` Organization 멤버, 레포 쓰기 권한)
- Claude Code (VS Code 확장) — 본인 Claude 요금제로 사용
- OpenDART 인증키 — 본인 계정으로 발급 (https://opendart.fss.or.kr). **키는 공유하지 않습니다**

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
5. 프로젝트 폴더에 `.env` 파일을 만들고 한 줄 저장: `DART_API_KEY=본인키`
   (`.env`는 GitHub에 올라가지 않게 설정되어 있음)

## 3. 수집 자료 받기

- 전체 표본 수집은 임근영 PC에서 진행 중이며 **11월 14일 전후 완료** 예정입니다
- 완료되면 `data` 폴더 압축본(약 5~6GB)을 구글 드라이브 등으로 전달합니다. 프로젝트 폴더에 `data`로 풀면 됩니다
- `data/pilot_control_map.csv`에는 현재 상장 기업 실명이 있어 **팀 내부에서만** 보관합니다
- KIND 원자료(`data/raw/`)도 압축본에 포함됩니다
- 자료를 받기 전에 코드를 미리 짜 보려면, 본인 키로 파일럿 노트북(`notebooks/03_pilot_mscore.ipynb`)을 실행해 16개 기업 자료를 받아 시험할 수 있습니다 (호출 수백 건)

## 4. Claude Code에서 시작하기

1. VS Code에서 프로젝트 폴더를 열고 Claude Code 창을 엽니다
2. Claude Code는 `CLAUDE.md`(작업 규칙·진행 상황·역할 분담)를 자동으로 읽습니다
3. 첫 요청 예시:
   > CLAUDE.md, docs/research_design.md, docs/HANDOFF.md를 읽고 지금까지 진행 상황과 내 담당 작업(패널 구성)을 요약해줘. 그다음 src/panel.py 설계안을 제안해줘.

## 5. 지켜야 할 규칙 (CLAUDE.md 요약)

- 기준 문서는 `docs/research_design.md`. 연구 설계 결정(표본·라벨·변수·모형·기준값)은 팀과 정한 뒤 이 문서에 먼저 기록
- **다른 사람 담당 모듈은 고치지 않고 import해서 씁니다**
  - 공동: `src/dart.py`, `src/labels.py`, `src/mscore.py`
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

사건 시점·"사유 발생 후" 표시, 미래 정보 누출 방지 원칙은 `docs/research_design.md` 3절·7절을 따릅니다.
