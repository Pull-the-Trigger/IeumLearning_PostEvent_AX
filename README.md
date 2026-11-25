# IeumLearning_PostEvent_AX
코드프레소 FDE Followship 기업 과제 | B2B 기업교육 서비스의 AI 기반 행사 후속 관리 프로세스 개선 및 고객 커뮤니케이션 자동화

## 폴더 구조

### 데이터 (data 브랜치)
```
data/
├── raw/          # 원본 엑셀 (GitHub 미업로드, 테스트 파일 E07만 포함)
├── ref/          # 참고 자료 (KSIC 제11차 분류체계 엑셀)
└── processed/    # 실행 결과 (GitHub 미업로드)
docs/
└── data-schema.md        # 데이터 테이블 구조와 규칙
src/
└── data/
    ├── build_profile.py      # 원본 → 통합 프로필 (메인 실행 파일)
    ├── mapping.json          # 열 이름 사전, 값 변환 규칙
    ├── make_ksic.py          # KSIC 엑셀 → ksic.json (한 번만 실행)
    ├── ksic.json             # 산업분류 목록 (대분류 21, 중분류 77)
    ├── classify_industry.py  # 회사 산업군 LLM 분류
    ├── industry_llm.json     # LLM 분류 결과
    └── industry_manual.json  # 사람이 수정한 값 (LLM보다 우선)
```

## 실행 방법

### 데이터 준비
1. 원본 엑셀을 `data/raw/`에 넣기
2. `python src/data/build_profile.py`
3. 결과: `data/processed/profiles.json`

자세한 구조와 규칙은 [docs/data-schema.md](docs/data-schema.md)를 봐 주세요.
