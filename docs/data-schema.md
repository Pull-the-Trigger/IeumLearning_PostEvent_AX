# 표준 데이터 스키마

이음러닝 행사 후속 관리용 원본 엑셀(`data/raw/`)을 아래 7개 표로 바꿉니다.
변환 규칙은 `src/data/mapping.json`에 있고, 실행은 `src/data/build_profile.py`로 합니다.

- 사람은 **이메일**로 구분합니다 (소문자로 바꾸고 앞뒤 공백 제거). 이름은 동명이인이 있어서 키로 쓰지 않습니다.
- 회사명은 `(주)`, `㈜`, `주식회사`, 띄어쓰기를 지워서 통일합니다 (`(주)동명메디칼` → `동명메디칼`).
- Y/N 값: 참석 `참석·O·출석 → Y`, `불참·X·결석 → N` / 수신 동의 `동의·Y·예 → Y`, `미동의·N·아니오 → N`.

## Event — 행사 (`00_행사목록_2026년3분기.xlsx`)

| 열 | 타입 | 뜻 | 원본 열 |
|---|---|---|---|
| event_id | 문자 | 행사 ID (E01~) | 행사 ID |
| event_name | 문자 | 행사명 | 행사명 |
| event_date | 날짜 | 개최일 | 개최일 |
| event_type | 문자 | 유형 | 유형 |
| applied_count | 정수 | 신청 인원 | 신청 인원 |
| attended_count | 정수 | 참석 인원 | 참석 인원 |
| thanks_mail_date | 날짜 | 감사 메일 발송일 (“발송하지 못함”은 빈 값) | 감사 메일 발송일 |
| thanks_mail_sent | Y/N | 감사 메일 발송 여부 | 감사 메일 발송일에서 계산 |
| survey_count | 정수 | 설문 응답 수 | 설문 응답 수 |
| note | 문자 | 비고 | 비고 |

## Customer — 사람 (참가자 명단에서 생성, 1명 1행)

| 열 | 타입 | 뜻 | 원본 |
|---|---|---|---|
| email | 문자 | 사람 키 | 명단의 이메일 열 |
| name | 문자 | 이름 | 가장 최근 행사 명단의 값 |
| company | 문자 | 회사명 (정규화) | 〃 |
| company_key | 문자 | Company 표와 연결하는 키 (= company) | 〃 |
| title | 문자 | 직함 | 〃 |
| consent | Y/N | 마케팅 수신 동의 | 〃 |
| first_event_id / last_event_id | 문자 | 처음 / 마지막 신청 행사 | 명단 파일 이름의 행사 ID |

## Company — 회사 (`companies.csv`, Customer에서 생성, 1개 회사 1행)

> **규칙: industry 필드는 내부용입니다** (영업 전달 카드, 성과 분석, 고객군 제안).
> 고객에게 가는 메일 문장에는 쓰지 않습니다.

| 열 | 타입 | 뜻 | 원본 |
|---|---|---|---|
| company_key | 문자 | 기본키. 정규화된 회사명 (Customer와 같은 규칙) | Customer의 company |
| company_name | 문자 | 표시용 회사명 | 명단의 회사명 원본 중 가장 많이 나온 값 |
| domain | 문자 | 이메일 도메인 | 그 회사 사람들 이메일 도메인 중 가장 많이 나온 값 |
| industry_major | 문자 | KSIC 대분류 코드+이름 (예: `C 제조업`) | industry_mid에서 ksic.json으로 찾음 |
| industry_mid | 문자 | KSIC 중분류 코드+이름 (예: `26 전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업`) | 아래 분류 방식 |
| industry_source | 문자 | `manual`(사람이 확인·수정) / `llm`(LLM 추정) / 빈칸(미분류) | |

`profiles.json`·`profiles_test.json`의 각 사람에도 `industry_major`, `industry_mid` 두 필드가 `company` 바로 뒤에 들어갑니다 (회사가 Company에 없거나 미분류면 `null`).

**KSIC 출처**: 한국표준산업분류 제11차 개정 (통계청 고시 제2024-2호, 2024-07-01 시행), 통계분류포털 자료실 2024-06-26 게시본
(`data/ref/한국표준산업분류_제11차_분류체계.xlsx`의 "11차개정한국표준산업분류" 시트).
`src/data/make_ksic.py`가 대분류 21개·중분류 77개만 뽑아 `src/data/ksic.json`으로 만듭니다 (개수가 다르면 멈춤).

**분류 방식** (`src/data/classify_industry.py`)

1. **확정 사전** `src/data/industry_manual.json` — `{"동명화학": "20"}`처럼 회사 키 → 중분류 코드. 여기 있으면 그 값을 쓰고 `manual`, LLM은 부르지 않습니다. `""`은 "사람이 확인했지만 미분류".
2. **LLM** — 기본 실행에서 `.env`에 `OPENAI_API_KEY`가 있으면 자동으로 (`--no-classify`로 끌 수 있음), 1에도 지난 결과(`src/data/industry_llm.json`)에도 없는 회사의 회사명+도메인을 50개씩 묶어 OpenAI API에 보내고 중분류 코드 하나만 고르게 합니다 (주된 사업 하나, 확신 없으면 빈칸). 결과는 `src/data/industry_llm.json`에 쌓여 다음 실행부터 LLM 없이 재사용되며 `llm`으로 표시됩니다. 대분류는 LLM에 묻지 않습니다.
3. **사람이 수정** — 틀린 값은 `src/data/industry_manual.json`에 직접 고쳐 넣으면 다음 실행부터 반영됩니다 (확인용 화면은 없음).

**두 파일의 관계** (둘 다 처음엔 `{}`, 형식은 `{company_key: 중분류 코드}`로 같음, 둘 다 커밋 대상)

| 순서 | 파일 | 누가 쓰나 | industry_source |
|---|---|---|---|
| 1 | `src/data/industry_manual.json` | 사람이 수정한 값, LLM 결과보다 우선 | `manual` |
| 2 | `src/data/industry_llm.json` | 기본 실행의 LLM 분류 (LLM 결과를 쌓아 둠) | `llm` |
| 3 | 둘 다 없음 | | 빈칸 (미분류) |

같은 회사가 두 파일에 다 있으면 `industry_manual.json`이 이깁니다. 그래서 LLM 결과를 고칠 때 `industry_llm.json`은 건드리지 않고 `industry_manual.json`에만 추가하면 됩니다.

`data/processed/companies.csv`(회사 표)는 이 두 파일과 별개로, 실행할 때마다 다시 만들어지는 결과물입니다.

목록에 없는 코드(사전·LLM 모두)는 `errors.csv`에 남기고 빈칸으로 둡니다.

## Participation — 신청 1건 1행 (`01_참가자명단_E0X_*.xlsx`)

| 열 | 타입 | 뜻 | E01·E04 | E02·E05 | E03·E06 |
|---|---|---|---|---|---|
| event_id | 문자 | 행사 ID | 파일 이름 | 파일 이름 | 파일 이름 |
| email | 문자 | 이메일 (필수) | 이메일 | 메일 주소 | E-mail |
| name | 문자 | 이름 (필수) | 이름 | 성함 | 신청자명 |
| company | 문자 | 회사명 (정규화) | 회사 | 소속 | 회사명 |
| company_raw | 문자 | 회사명 원본 | 회사 | 소속 | 회사명 |
| title | 문자 | 직함 | 직함 | 직책 | 직급/직책 |
| pre_question | 문자 | 사전 질문 | 사전 질문 | 궁금한 점 | 질문사항 |
| attended | Y/N | 참석 여부 (필수) | 참석 | 출석여부 | 출석 |
| consent | Y/N | 마케팅 수신 동의 | 마케팅 수신 동의 | 뉴스레터 수신 | 수신동의 여부 |
| note | 문자 | 자유 기입 (비고·메모 열이 들어오면 여기로) | – | – | – |
| source_file / source_row | 문자 / 정수 | 원본 파일과 엑셀 행 번호 | | | |
| is_test | 참/거짓 | 테스트 행사 여부 (`mapping.json`의 test_events) | | | |

E03·E06의 `No`(순번) 열은 무시합니다.

## Survey — 만족도 설문 (`02_만족도설문_문항과응답.xlsx`, 응답 시트)

| 열 | 타입 | 뜻 | 원본 열 |
|---|---|---|---|
| survey_id | 문자 | 응답 ID (S001~) | 행 순서 |
| event_id | 문자 | 행사 ID | 행사 ID |
| response_date | 날짜 | 응답일 | 응답일 |
| q1_satisfaction | 정수 1–5 | 전반 만족도 | Q1 만족도 |
| q2_helpfulness | 정수 1–5 | 업무 도움 정도 | Q2 도움 정도 |
| q3_recommend | 정수 0–10 | 추천 의향 | Q3 추천 의향 |
| q4_helpful_content | 문자 | 가장 도움이 된 내용 | Q4 도움이 된 내용 |
| q5_wanted_topic | 문자 | 듣고 싶은 주제 | Q5 듣고 싶은 주제 |
| q6_adoption | Y/REVIEW/N | 도입 검토 (예/검토 중/아니오) | Q6 도입 검토 |
| q7_contact_wish | Y/N | 담당자 연락 희망 | Q7 연락 희망 |
| email | 문자 | 이메일 (선택, 없으면 빈 값) | Q8 이메일 |
| matched | Y/N | 참가자 명단의 사람과 연결됐는지 | 계산 |

## Interaction — 후속 연락 (`04_후속연락기록_담당자메모.xlsx`)

| 열 | 타입 | 뜻 | 원본 열 |
|---|---|---|---|
| interaction_id | 문자 | 기록 ID (I001~) | 행 순서 |
| event_id | 문자 | 행사 ID | 행사 ID |
| name | 문자 | 이름 | 이름 |
| company | 문자 | 회사명 (정규화) | 회사 |
| contact_date | 날짜 | 연락일 | 연락일 |
| method | 문자 | 연락 방법 | 방법 |
| memo | 문자 | 담당자 메모 | 메모 |
| result | 문자 | 결과 | 결과 |
| email | 문자 | 연결된 사람 | 이메일이 없어서 **행사 + 이름 + 회사**로 명단에서 찾아 채움 |

## Content — 발행 글 (`03_발행글목록_2026년3분기.xlsx`)

| 열 | 타입 | 뜻 | 원본 열 |
|---|---|---|---|
| content_id | 문자 | 글 ID (C001~) | 번호 |
| published_date | 날짜 | 발행일 | 발행일 |
| channel | 문자 | 채널 | 채널 |
| title | 문자 | 제목 | 제목 |
| topic | 문자 | 주제 | 주제 |
| audience | 문자 | 대상 독자 | 대상 독자 |
| url | 문자 | 링크 | 링크 |

## 참가자 명단의 열 이름 변환 순서

1. 사전(`mapping.json`의 columns)과 정확히 일치
2. 띄어쓰기·대소문자·기호를 지우고 비교 (`메일주소` = `메일 주소`)
3. 핵심 단어 포함 여부 (메일→email, 질문·궁금→pre_question, 참석·출석→attended, 동의·수신→consent,
   회사·소속→company, 직함·직책·직급→title, 비고·메모→note, 이름·성명·~명→name)
4. 값으로 검증 (email은 `@` 포함, attended·consent는 값 사전에 있는 값).
   3단계 후보가 검증에 실패하면 다음 후보로 다시 시도합니다 (`이메일 수신 동의` → email 실패 → consent).

이걸로도 못 맞춘 열은 변환하지 않고 `data/processed/errors.csv`에 남깁니다. 필수값 누락도 같은 파일에 남습니다.
이메일 열을 못 찾은 명단이 있으면 통합 프로필을 만들지 않고 멈춥니다.

---

## 실행 방법

> **실행 전 각자 가진 원본 엑셀을 `data/raw/` 에 넣어주세요.** (원본은 깃헙에 올라가지 않습니다)

pandas 2.x와 3.x 둘 다 됩니다 (2.3.3, 3.1.1에서 확인했고 결과 파일이 똑같이 나옵니다).
빈칸은 pandas 버전과 상관없이 항상 None(JSON에서는 `null`)으로 저장되고, JSON에 NaN이 섞이면 저장할 때 바로 오류가 납니다.

```bash
pip install pandas openpyxl
pip install openai                       # 산업군 LLM 분류를 쓸 때만 필요
python src/data/build_profile.py              # 변환 + 산업군 분류 + 통합 프로필 + 확인 출력
python src/data/build_profile.py --no-classify  # LLM 산업군 분류 없이 실행
python src/data/build_profile.py --make-test  # 테스트 명단(E07)을 다시 만들 때
python src/data/make_ksic.py                  # KSIC 엑셀이 바뀌었을 때만 (src/data/ksic.json 재생성)
```

- 기본 실행은 `industry_manual.json`·`industry_llm.json` 어디에도 없는 회사만 LLM으로 분류해 `industry_llm.json`에 쌓습니다.
  이미 모두 분류됐으면 LLM을 부르지 않습니다. `--no-classify`를 주면 LLM 없이 두 파일의 값만 씁니다.
- LLM 설정: `.env`에 `OPENAI_API_KEY`, `OPENAI_MODEL`을 적는다 (`.env`는 깃헙에 올라가지 않음).
  `OPENAI_API_KEY`는 필수, `OPENAI_MODEL`은 선택(없으면 `gpt-4.1-mini`).
  키나 `openai` 패키지가 없으면 경고만 내고 미분류 회사는 빈칸으로 둔 채 정상 종료합니다.
- 원본은 수정하지 않고 결과는 `data/processed/`에 저장합니다:
  `events.csv`, `customers.csv`, `companies.csv`, `participation.csv`, `surveys.csv`, `interactions.csv`, `contents.csv`, `errors.csv`,
  `profiles.json`(원본 6개 행사), `profiles_test.json`(테스트 명단만)
- `data/raw/01_*.xlsx`는 모두 자동으로 읽힙니다. 새 열 이름은 `mapping.json`에 추가하면 됩니다.
- 확인 항목 중 FAIL이 있거나 실행이 멈추면 종료 코드 1을 돌려줍니다.

## 확인 결과 (2026-11-24 실행)

원본 6개 행사 — 모두 OK

| 항목 | 기대 | 실제 |
|---|---|---|
| 신청 | 306 | 306 |
| 참석 | 250 | 250 |
| 실제 참석자 | 232명 | 232명 |
| 2회 이상 참석 | 18명 | 18명 |
| 참석자 수신 동의 Y / N | 174 / 58명 | 174 / 58명 |
| 설문 / 이메일 없음 / 그중 연락 희망 | 45 / 20 / 8 | 45 / 20 / 8 |
| 후속연락기록 / 참가자 연결 | 25 / 25 | 25 / 25 |
| profiles.json 인원 | 283명 = 참석자 232 + 신청만 한 사람 51 | 283명 = 232 + 51 |

테스트 명단 `01_참가자명단_E07_테스트행사.xlsx` — 모두 OK (profiles.json에는 섞이지 않음)

| 원본 열 | 결과 | 단계 |
|---|---|---|
| No | 무시 | 무시 목록 |
| 소속 / 비고 | company / note | ① 정확 일치 |
| 직 급 / 메일주소 / 사전질문 | title / email / pre_question | ② 기호·띄어쓰기 제거 |
| 참가자명 / 참석 체크 | name / attended | ③ 핵심 단어 |
| 이메일 수신 동의 | consent | ③ email 후보가 ④ 검증 실패 → 다음 후보 consent |
| 관심 분야 | 오류 목록 | 매칭 실패 |

- 이메일이 빈 행 1건 → 오류 목록(필수값 누락), 프로필에서 제외
- profiles_test.json 3명: 이메일 소문자화(`Test01@Test.example` → `test01@test.example`), 회사명 정규화(`테스트 솔루션㈜` → `테스트솔루션`), O/X·동의/미동의 → Y/N, 비고 → note 확인
- 이메일 열 이름을 바꾼 명단으로 따로 실행 → 통합 프로필을 만들지 않고 멈추는 것 확인

## 통합 프로필 예시 (이름·이메일 가림)

2회 참석 + 설문 응답:

```json
{
  "email": "us***@co01chem.example",
  "name": "백*윤",
  "company": "동명화학",
  "title": "부사장",
  "consent": "Y",
  "first_event_id": "E01",
  "last_event_id": "E05",
  "applied_count": 3,
  "attended_count": 2,
  "events": [
    {"event_id": "E01", "event_name": "CEO 인사이트 특강 (서울)", "event_date": "2026-07-09", "attended": "Y", "pre_question": null, "note": null},
    {"event_id": "E02", "event_name": "HR 담당자 AI 특강", "event_date": "2026-07-23", "attended": "Y", "pre_question": "사내 자료를 넣어도 되는지 기준이 있나요?", "note": null},
    {"event_id": "E05", "event_name": "실무자 AI 교육 설명회", "event_date": "2026-09-10", "attended": "N", "pre_question": "사내 자료를 넣어도 되는지 기준이 있나요?", "note": null}
  ],
  "surveys": [
    {"survey_id": "S004", "event_id": "E01", "response_date": "2026-07-13", "q1_satisfaction": 3, "q2_helpfulness": 5, "q3_recommend": 8,
     "q4_helpful_content": "질의응답 시간", "q5_wanted_topic": "직무별 AI 교육 과정", "q6_adoption": "REVIEW", "q7_contact_wish": "Y", "matched": "Y"}
  ],
  "interactions": []
}
```

설문 응답 + 후속 연락:

```json
{
  "email": "us***@co08sol.example",
  "name": "권*진",
  "company": "신화솔루션",
  "title": "전무",
  "consent": "N",
  "first_event_id": "E04",
  "last_event_id": "E04",
  "applied_count": 1,
  "attended_count": 1,
  "events": [
    {"event_id": "E04", "event_name": "CEO 인사이트 특강 (부산)", "event_date": "2026-08-27", "attended": "Y", "pre_question": null, "note": null}
  ],
  "surveys": [
    {"survey_id": "S028", "event_id": "E04", "response_date": "2026-08-27", "q1_satisfaction": 5, "q2_helpfulness": 4, "q3_recommend": 9,
     "q4_helpful_content": "규정을 만든 과정", "q5_wanted_topic": "현업 부서 자동화", "q6_adoption": "REVIEW", "q7_contact_wish": "Y", "matched": "Y"}
  ],
  "interactions": [
    {"interaction_id": "I015", "event_id": "E04", "contact_date": "2026-09-09", "method": "전화",
     "memo": "사내 규정 사례를 궁금해함", "result": "다음 분기에 다시 연락하기로 함"}
  ]
}
```
