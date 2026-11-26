# frontend

행사 후속 관리 화면입니다 (Next.js). 담당: 수민

## 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:3000 을 엽니다.

## 화면

| 화면 | 경로 |
|---|---|
| 대시보드 | `/` |
| 감사 메일 | `/follow-up/thank-you` |
| 맞춤 메일 (메뉴 이름 "개인 맞춤 메일") | `/follow-up/personal-mail` |
| 뉴스레터 | `/broadcast/newsletter` |
| 설문 관리 | `/follow-up/survey` |
| 참가자용 설문 | `/survey/[token]` (미리보기 `/survey/preview/[token]`) |

메뉴에 있는 나머지 화면은 아직 준비 중 화면으로 표시됩니다.

## 데이터

지금은 `frontend/lib/`의 시연용 가짜 데이터(`dashboard-data.ts`, `thank-you-mail-data.ts`, `personal-mail-data.ts`, `newsletter-data.ts`, `survey-data.ts`)를 씁니다.
백엔드(`backend/`)와는 아직 연결 전입니다.
