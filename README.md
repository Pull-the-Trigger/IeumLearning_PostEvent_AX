# IeumLearning_PostEvent_AX
코드프레소 FDE Followship 기업 과제 | B2B 기업교육 서비스의 AI 기반 행사 후속 관리 프로세스 개선 및 고객 커뮤니케이션 자동화

## 폴더 구조

```
frontend/              # 행사 후속 관리 화면 (Next.js)
backend/               # Python 스크립트
├── data/              # 원본 엑셀 → 표준 표·통합 프로필, 산업군 분류
├── thanks_mail/       # 감사 메일 초안
├── custom_mail/       # 맞춤 메일 초안 + 영업 전달 패키지
├── pre_question/      # 사전 질문 분류 → 출석자별 후속 연락 계획
├── reply_classifier/  # 회신 메일 분류 + 답장 초안
└── test_data/         # 사전 질문 시험지 생성
data/
├── raw/               # 원본 엑셀 (E07 테스트 파일만 GitHub에 올림)
├── ref/               # 참고 자료 (KSIC 제11차 분류체계 엑셀)
├── test/              # 테스트 회신·사전 질문 시험지
└── processed/         # backend/data/build_profile.py 결과
docs/                  # 데이터 구조·기능 문서
out/                   # 메일 초안·분류 결과
```

## 시작하기

- **백엔드**: `pip install -r backend/requirements.txt` 후 [backend/README.md](backend/README.md)의 순서대로 실행
- **프론트**: [frontend/README.md](frontend/README.md)
- **`.env`**: 저장소 루트에 `OPENAI_API_KEY`, `OPENAI_MODEL`을 적습니다. 없어도 LLM 없이 실행됩니다. **커밋하지 마세요.**

## 데이터 주의

참석자 정보가 들어 있어 아래는 GitHub에 올리지 않습니다 (`.gitignore`).
- `data/raw/` 원본 엑셀 (E07 테스트 파일 제외)
- `data/processed/`
- `out/`

## 작업 규칙

- **브랜치**
  - `main`: 발표·배포용. PR로만 합칩니다.
  - `develop`: 통합 브랜치
  - 이름/작업 브랜치: `develop`에서 따고, PR로 합친 뒤 삭제합니다.
- **커밋 메시지**: `feat:` 기능 / `fix:` 버그 수정 / `refactor:` 구조 변경 / `docs:` 문서
- 코드를 바꾼 사람이 같은 PR에서 관련 문서(docs, README, requirements)도 함께 고칩니다.

## 문서

- [backend/README.md](backend/README.md): 설치, 실행 순서, 기능 폴더
- [frontend/README.md](frontend/README.md): 화면 실행, 화면 목록
- [docs/data-schema.md](docs/data-schema.md): 데이터 표 구조와 규칙
- [docs/thank-you-mail.md](docs/thank-you-mail.md): 감사 메일
- [docs/custom-mail.md](docs/custom-mail.md): 맞춤 메일 + 영업 전달
- [docs/pre-question.md](docs/pre-question.md): 사전 질문 → 후속 연락 계획
- [docs/reply-classifier.md](docs/reply-classifier.md): 회신 메일 분류
