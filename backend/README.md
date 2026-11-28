# backend

행사 데이터를 정리하고 메일 초안·연락 계획·회신 분류를 만드는 Python 스크립트입니다.
모든 명령은 **저장소 루트에서** 실행합니다.

## 설치

가상환경(`.venv`, git에는 올라가지 않음)을 만들고 그 안에 설치합니다.

```bash
python -m venv .venv                              # 처음 한 번
source .venv/bin/activate                         # 새 터미널을 열 때마다
python -m pip install -r backend/requirements.txt
which python                                      # .../.venv/bin/python 이 나와야 함
```

- 새 터미널마다 `source .venv/bin/activate`를 다시 실행해야 합니다.
- 주의: `~/.zshrc`에 `alias python=...`가 있으면 가상환경을 켜도 다른 python이 실행됩니다. `which python`으로 `.venv` 경로인지 확인하세요.

LLM 설정은 루트 `.env`에 `OPENAI_API_KEY`, `OPENAI_MODEL`을 적습니다. 키가 없으면 LLM 없이 실행됩니다.

## 실행 순서

원본 엑셀을 `data/raw/`에 넣은 뒤 아래 순서로 실행합니다.

### 1. 데이터 준비: `backend/data/` → `data/processed/`
```bash
python backend/data/build_profile.py                # 변환 + 산업군 분류 + 통합 프로필 + 확인 출력
python backend/data/build_profile.py --no-classify  # LLM 산업군 분류 없이 실행
python backend/data/build_profile.py --make-test    # 테스트 명단(E07)을 다시 만들 때
python backend/data/make_ksic.py                    # KSIC 엑셀이 바뀌었을 때만 (backend/data/ksic.json 재생성)
python backend/db/load.py                           # build_profile.py 다음에: data/processed/*.csv → SQLite (data/processed/ieum.db)
                                                    # out/thanks_mails.csv 가 있으면 감사 메일 초안도 넣음 (없으면 안내만, 2번 뒤 다시 실행)
```

### API 서버 (데이터 관리·감사 메일 승인·개인 맞춤 메일·개인 맞춤 콘텐츠 화면용): `backend/app/` ← `data/processed/ieum.db`, `out/custom_mails.csv`

> **현재 로그인·접근 제한 없음. 로컬 개발·시연용이며 서버 배포 전 인증 필요.**

```bash
python backend/db/load.py              # DB가 없거나 CSV가 바뀌었으면 먼저
python backend/custom_mail/build_mails.py --include-drafts  # /personal-mail 용 맞춤 메일 초안 (out/custom_mails.csv)
uvicorn backend.app.main:app --reload  # http://127.0.0.1:8000 (문서 페이지: /docs)
```
조회는 GET, 감사 메일 승인·취소만 POST입니다. 응답 필드는 화면 타입과 같은 camelCase입니다.

| 주소 | 내용 |
|---|---|
| `/health` | 서버·DB 확인 (DB가 없으면 503) |
| `/events` | 행사 |
| `/customers` | 고객 (산업군, 신청·참석 횟수, 설문 응답 여부 포함) |
| `/participation` | 행사별 신청 (행사명, 설문 답, 후속연락 메모 포함) |
| `/surveys` | 설문 응답 (행사명, 고객 연결 상태 포함) |
| `/interactions` | 후속 연락 기록 (행사명 포함) |
| `/contents` | 발행 글 |
| `GET /thanks` | 감사 메일 행사별 요약: `eventId`, `eventName`, `eventDate`, `draftCount`, `excludedCount`, `status`, `sendBy`, `sendByPassed`, `scheduledAt`(있으면), `sentAt`(있으면) |
| `GET /thanks/{event_id}` | 위 요약 + `recipients`: `draftId`, `email`, `name`, `company`, `title`, `subject`, `body`, `sender`, `surveyIncluded`, `approvalStatus`(`none`/`scheduled`/`sent`/`excluded`), `approvalInvalid` |
| `POST /thanks/{event_id}/approve` | 본문 `{mode: "now" \| "scheduled", scheduledAt?: "YYYY-MM-DD HH:MM", excludedEmails?: []}`. 과거 예약 400, 발송 기한 이후 예약은 저장 + `warnings`, 이미 발송 409, 발송 예정이면 덮어씀 |
| `POST /thanks/{event_id}/cancel` | 발송 예정(예약 시각 전)일 때만 그 행사 승인 기록 삭제. 발송 완료 409 |
| `/personal-mail` | 개인 맞춤 메일 화면: 행사별 받는 사람(맞춤 메일 대상만), AI 초안, 갈래·약속·승인 방식. DB가 아니라 `out/custom_mails.csv`를 읽음 (`backend/app/personal_mail.py`) |
| `/personal-content` | 개인 맞춤 콘텐츠 화면: 발행 글마다 추천 고객. R01 질문·R04 교류·R02 관심 주제·R06 불참 신청자 후기는 마케팅 발송, R03 도입 검토는 영업 담당 전달, R05 직무는 글 고를 때만. 수신 동의자만, 맞춤 메일에서 보낸 글 제외, 2주에 1편은 화면에서 보낼 때 막음 (`backend/app/personal_content.py`) |

감사 메일 상태 규칙 (`backend/app/mail_approvals.py`, 행사 단위, 화면 값과 같음):
- `draft` 초안 없음 / `review` 초안은 있고 유효한 승인 없음 / `scheduled` 예약 시각 전 / `sent` 지금 발송했거나 예약 시각이 지남
- 승인 당시 `body_hash`(제목+본문)가 지금 초안과 다르면 승인 무효(`approvalInvalid`) → 발송 전이면 행사는 `review`. 이미 발송된 행사는 `sent` 유지
- 시간은 Asia/Seoul, 저장 형식 `YYYY-MM-DD HH:MM:SS`. **실제 메일은 보내지 않고 상태만 기록합니다.**
- 먼저 `build_thanks.py` → `load.py`로 초안을 DB에 넣어야 합니다 (메일 표가 없으면 503).

`/customers` 필드 참고:
- `interests`: 그 고객의 설문 Q5(듣고 싶은 주제)를 중복 없이 최근 응답 순으로 `", "` 연결 (설문이 없거나 Q5가 비면 `""`)
- `existingCustomer`: DB에 등록된 행사 중 참석(`attended='Y'`) 2회 이상이면 `"Y"`, 아니면 `"N"`
- `role` 필드는 없음 (직무 분류는 화면에서 계산)

설정은 루트 `.env`의 `DB_PATH`(DB 위치), `CORS_ORIGINS`(허용할 화면 주소, 기본 `http://localhost:3000`, `http://127.0.0.1:3000`)입니다. `.env.example` 참고.

### 2. 감사 메일: `backend/thanks_mail/` → `out/thanks_mails.csv`
```bash
python backend/thanks_mail/build_thanks.py
python backend/db/load.py                    # 감사 메일 초안을 DB(mail_drafts, mail_type='thanks')에 넣기
```
옵션: `--config`, `--template`, `--signature`, `--out` (다른 설정·문안으로 시험할 때)

`load.py`는 `mail_drafts`의 thanks 행만 지우고 다시 넣고, 승인 기록(`mail_approvals`)은 지우지 않습니다. 다른 위치의 CSV는 `--thanks-csv`로 지정합니다.

### 3. 출석자별 후속 연락 계획: `backend/pre_question/` → `out/followup_plan.csv`
```bash
python backend/pre_question/plan_followups.py [--out out/followup_plan]
```

### 4. 맞춤 메일 + 영업 전달: `backend/custom_mail/` → `out/custom_mails.csv`, `out/sales_handoff.csv`
```bash
python backend/custom_mail/build_mails.py                   # 메일 보내는 날까지 발행된 글만 사용 (실제 상황)
python backend/custom_mail/build_mails.py --as-of today     # 지금 있는 글 전부 사용 (다음 행사 시연용)
python backend/custom_mail/build_mails.py --include-drafts  # 검수 전 답변까지 넣어 미리 보기
```
내부에서 3번(`plan_followups.py`)을 먼저 돌립니다.

### 5. 회신 분류: `backend/reply_classifier/` → `out/reply_results.json` / `.csv`
```bash
python backend/reply_classifier/classify_replies.py data/test/test_replies.json  # [--out out/reply_results] [--today YYYY-MM-DD]
python backend/reply_classifier/evaluate.py data/test/test_replies.json          # 정확도 측정
```

### 평가·테스트 도구
```bash
python backend/pre_question/evaluate_pre.py data/test/pre_question_tests.json   # 사전 질문 분류 채점 ('문장 사전만' vs '사전 + AI')
python backend/test_data/make_pre_question_tests.py                             # 사전 질문 시험지 생성 (data/test/pre_question_tests.json을 덮어씀)
```

## 기능 폴더

| 폴더 | 하는 일 | 담당 | 문서 |
|---|---|---|---|
| `data/` | 원본 엑셀 → 표준 표·통합 프로필, 회사 산업군 분류 | 나혜 | [docs/data-schema.md](../docs/data-schema.md) |
| `thanks_mail/` | 감사 메일 초안 | 나혜 | [docs/thank-you-mail.md](../docs/thank-you-mail.md) |
| `custom_mail/` | 맞춤 메일 초안 + 영업 전달 패키지 | 소민 | [docs/custom-mail.md](../docs/custom-mail.md) |
| `pre_question/` | 사전 질문 분류 → 출석자별 후속 연락 계획 | 소민 | [docs/pre-question.md](../docs/pre-question.md) |
| `reply_classifier/` | 회신 메일 분류 + 답장 초안 | 소민 | [docs/reply-classifier.md](../docs/reply-classifier.md) |
| `test_data/` | 사전 질문 시험지 생성 | 소민 | — |
