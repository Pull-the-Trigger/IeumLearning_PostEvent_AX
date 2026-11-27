# backend

행사 데이터를 정리하고 메일 초안·연락 계획·회신 분류를 만드는 Python 스크립트입니다.
모든 명령은 **저장소 루트에서** 실행합니다.

## 설치

```bash
pip install -r backend/requirements.txt
pip install openai          # LLM(OpenAI)을 쓸 때만
```

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
```

### 2. 감사 메일: `backend/thanks_mail/` → `out/thanks_mails.csv`
```bash
python backend/thanks_mail/build_thanks.py
```
옵션: `--config`, `--template`, `--signature`, `--out` (다른 설정·문안으로 시험할 때)

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
