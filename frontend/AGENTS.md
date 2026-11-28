<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# 프론트엔드 공통 개발 가이드

이 문서는 `frontend/` 디렉터리의 화면 개발 및 수정에 적용한다. 프로젝트 전체 규칙은 루트 [AGENTS.md](../AGENTS.md)를 따르며, 이 문서는 현재 프론트엔드 구현에서 확인되는 규칙과 재사용 지점을 보완한다.

## 1. 적용 원칙

- 기존 디자인 토큰, 레이아웃, 공통 컴포넌트를 먼저 확인하고 재사용한다.
- 유사한 기능을 페이지별 JSX와 CSS로 중복 구현하지 않는다.
- 요청 범위를 벗어난 페이지, 전역 스타일, 데이터 구조를 임의로 변경하지 않는다.
- 실제 데이터, 목업 데이터, 발송 시뮬레이션, 미연동 상태를 구분해서 표시한다.
- 저장하지 않은 입력, 검토 상태, 승인 상태, 모달 검색·필터·페이지 상태를 사용자 확인 없이 초기화하지 않는다.
- 구현하지 않은 기능을 정상 작동하는 것처럼 표시하지 않는다.
- 화면 변경 후 TypeScript, ESLint, 프로덕션 빌드, `git diff --check`, 실제 브라우저 동작을 확인한다. 실행하지 않은 검증은 완료로 보고하지 않는다.

## 2. 기술 스택 및 구조

현재 [package.json](./package.json) 기준 기술 스택은 다음과 같다.

| 항목 | 현재 사용 기술 |
|---|---|
| 프레임워크 | Next.js 16.4.6, App Router |
| 언어 | TypeScript 5.9 계열 |
| UI | React 19.3.0, 함수형 컴포넌트 |
| 스타일 | `app/globals.css`의 일반 CSS 및 CSS 변수, Tailwind CSS/PostCSS 설정 |
| 아이콘 | `lucide-react` |
| 기타 | `qrcode`, `xlsx` |
| 폰트 | `Pretendard`, `Noto Sans KR`, `Malgun Gothic`, `system-ui` 순서 |

주요 경로:

- `app/`: App Router 페이지와 전역 레이아웃. 페이지 진입점은 `app/**/page.tsx`에 둔다.
- `components/`: 화면·레이아웃·기능 단위 컴포넌트. 현재 공통 레이아웃은 [app-shell.tsx](./components/app-shell.tsx), [header.tsx](./components/header.tsx), [sidebar.tsx](./components/sidebar.tsx)에 있다.
- `lib/`: 메뉴 설정, 화면 데이터, 타입, 규칙형 계산 및 변환 함수. 예: [navigation.ts](./lib/navigation.ts), [dashboard-data.ts](./lib/dashboard-data.ts), [thank-you-mail-data.ts](./lib/thank-you-mail-data.ts).
- [globals.css](./app/globals.css): 디자인 토큰과 공통·페이지별 스타일이 함께 정의되어 있다.
- [layout.tsx](./app/layout.tsx): `RootContent`를 통해 공통 셸을 제공하고 `globals.css`를 로드한다.

새 페이지는 먼저 유사한 기존 페이지의 구조와 CSS 선택자를 확인하고, 필요한 경우 새 스타일을 페이지 전용 클래스 아래에 제한한다.

## 3. 색상 및 디자인 토큰

기본 토큰은 [globals.css](./app/globals.css)의 `:root`에 있다.

| 역할 | 토큰 | 실제 값 |
|---|---|---|
| 메인 배경 | `--bg-main` | `#101319` |
| 상단 헤더 | `--bg-header` | `#191f29` |
| 사이드바 | `--bg-sidebar` | `#161b23` |
| 카드·모달 | `--bg-card` | `#1b222d` |
| 테두리·구분선 | `--border` | `#303b4a` |
| 기본 텍스트 | `--text` | `#e2e8f0` |
| 제목 텍스트 | `--heading` | `#f1f5f9` |
| 보조 텍스트 | `--muted` | `#9ba9bd` |
| 비활성 아이콘 | `--icon-muted` | `#8795a9` |
| 강조·검토 대기 | `--accent` | `#91b5ff` |
| 선택 영역 | `--active` | `#263a58` |
| 날짜 박스 | `--date-bg` | `#293344` |
| 완료 | `--complete` | `#6ee7b7` |
| 자료 등록·확인 필요 | `--warning` | `#fbbf77` |
| 오류·기한 초과 | `--danger` | `#f87171` |
| 기본 모서리 | `--radius` | `8px` |

공통 상태 클래스는 `.status-warning`, `.status-pending`, `.status-complete`, `.status-muted`, `.status-danger`를 사용하며 [status-text.tsx](./components/status-text.tsx)의 `StatusText`와 함께 사용한다. 버튼의 기본 파란색은 `--accent`, 보조 버튼은 투명 배경과 `--border` 테두리를 사용한다. 새 색상을 직접 추가하기 전에 기존 토큰으로 표현할 수 있는지 확인한다.

참고: 메일 미리보기는 실제 메일에 가까운 밝은 영역을 위해 `#f7f8fa`, `#1f2937` 등 별도 색상을 사용한다. 이는 앱 전체 배경 토큰을 대체하는 규칙이 아니다.

## 4. 타이포그래피

- 전역 `body`는 위 폰트 스택을 사용한다. 페이지에서 별도 폰트를 선언하지 않는다.
- 대시보드 제목 `h1`은 기본 `24px~30px` 범위, 메일 계열 페이지 제목도 `.mail-page h1`의 공통 규칙을 따른다.
- 섹션 제목은 `.section-header h2` 또는 `.mail-section-heading h2`의 `17px`, 카드 제목은 `.card-heading h2`의 `16px`을 기준으로 한다.
- 페이지 설명과 본문 보조 설명은 주로 `12px~13px`의 `--muted` 색상을 사용한다.
- 테이블 본문은 `.recipient-table`의 `11px`, 테이블 헤더는 `11px` 기준이다.
- 입력 필드와 버튼은 대체로 `12px`, 라벨은 `11px~12px`을 사용한다.
- 메일 본문은 일반 굵기(`font-weight: 400`)와 줄 간격 `1.65~1.8`을 사용한다. 전체 문안을 불필요하게 굵게 만들지 않는다.
- 긴 한글·URL·제목은 `overflow-wrap: anywhere`, 필요한 목록에서는 말줄임을 사용하여 다른 컬럼을 침범하지 않게 한다.

## 5. 레이아웃·여백

공통 셸은 [app-shell.tsx](./components/app-shell.tsx)에서 [header.tsx](./components/header.tsx)와 [sidebar.tsx](./components/sidebar.tsx)를 조합한다.

- 헤더는 `position: fixed`, 높이 `64px`, `z-index: 20`이다.
- 사이드바는 헤더 아래에 고정되고 폭은 `248px`, `z-index: 10`이다.
- 메인 콘텐츠는 `.main-content`의 `inset: 64px 0 0 248px`와 독립 스크롤을 사용한다.
- 대시보드 콘텐츠는 최대 `1360px`, 메일 계열 콘텐츠는 `.mail-page` 최대 `1440px`와 좌우 `32px` 패딩을 기준으로 한다.
- 메일 계열 페이지의 섹션은 `.mail-section` 간격 `26px`, 카드 내부 패딩 `20px`, 카드 간격 `16px`을 기준으로 한다.
- 카드 모서리는 `var(--radius)`의 `8px`을 사용한다.
- 번호 배지와 섹션 제목은 [thank-you-mail-page.tsx](./components/thank-you-mail-page.tsx)의 `CardTitle` 및 `.card-heading` 구조처럼 같은 행에 배치하고 `align-items: center`를 유지한다.
- 화면 폭이 줄어들면 기존 미디어 쿼리 기준으로 그리드를 2열 또는 1열로 전환한다. 고정 폭 때문에 가로 스크롤이 생기지 않도록 `min-width: 0`을 적용한다.

## 6. 재사용 가능한 컴포넌트와 실제 위치

현재 확인된 공통 컴포넌트는 다음과 같다.

| 기능 | 구현 위치 및 사용 규칙 |
|---|---|
| 헤더·사이드바·셸 | [app-shell.tsx](./components/app-shell.tsx), [header.tsx](./components/header.tsx), [sidebar.tsx](./components/sidebar.tsx) |
| 메뉴 설정 | [navigation.ts](./lib/navigation.ts). 사이드바와 홈 업무 카드의 상위 메뉴 명칭·아이콘 기준으로 재사용한다. |
| 섹션 헤더 | [section-header.tsx](./components/section-header.tsx). 대시보드 섹션의 제목·설명·전체 보기 링크에 사용한다. 메일 페이지의 번호형 헤더는 [thank-you-mail-page.tsx](./components/thank-you-mail-page.tsx)의 `CardTitle` 구조를 따른다. |
| 업무 요약 카드 | [task-summary-card.tsx](./components/task-summary-card.tsx). [dashboard-home.tsx](./components/dashboard-home.tsx)의 `taskGroups`와 연결한다. |
| 상태 표시 | [status-text.tsx](./components/status-text.tsx)의 `StatusText`와 `StatusTone`을 사용한다. |
| 빈 상태 | [empty-state.tsx](./components/empty-state.tsx)의 `EmptyState`를 사용한다. |
| 테이블·페이지네이션 | 현재 전용 테이블 클래스(`recipient-table`, `pagination`)가 [globals.css](./app/globals.css)에 정의되어 있다. 별도 공통 Table 컴포넌트로 추상화되어 있다고 가정하지 말고 기존 JSX 구조를 확인한다. |
| 검색·필터 | 공통 CSS 클래스 `.search-input`, `.filter-tabs`를 사용하지만 검색·필터 상태는 각 페이지가 관리한다. |
| 모달 | [thank-you-mail-page.tsx](./components/thank-you-mail-page.tsx), [personal-content-page.tsx](./components/personal-content-page.tsx), [survey-management-modal.tsx](./components/survey-management-modal.tsx)의 `createPortal(..., document.body)` 패턴을 기준으로 한다. |
| 날짜 선택 | 감사 메일의 `DatePicker`와 개인 맞춤 콘텐츠의 `DateField` 구현을 먼저 확인한다. 날짜 필드 전체를 버튼 트리거로 사용하고 연·월 이동, 날짜 선택, 외부 클릭·Escape 종료를 유지한다. |
| 시간 선택 | 감사 메일의 `TimePicker`를 재사용하고 오전·오후, 시, 분 값과 기존 저장 형식의 호환성을 유지한다. |
| 메일 작성 영역 | 감사 메일·개인 맞춤 메일의 기존 작성 컴포넌트와 `.template-editor`, `.draft-compose` 계열 스타일을 확인한다. 입력·본문·첨부파일의 기존 상태 관리와 검토 상태 갱신을 보존한다. |

`survey-management-modal.tsx`는 QR, 응답 목록, 상세 응답을 포함하는 기능별 모달이며 [survey-data.ts](./lib/survey-data.ts)와 연결된다. 공통 컴포넌트가 아닌 페이지 고유 컴포넌트는 다른 페이지에 그대로 복사하지 말고 필요한 공통화 범위를 먼저 확인한다.

## 7. 업무 현황 카드·상태 표시

- 같은 요약 카드 그룹은 동일한 열 수, 높이, 내부 패딩을 사용한다.
- `.personal-content-summary`처럼 상태명, 숫자·단위 그룹, 목록 보기 문구를 가운데 정렬하는 현재 구현을 유지한다.
- 상태 색상은 `작성 대기/자료 확인 필요=warning`, `검토 대기=accent`, `발송 예정=accent 또는 해당 페이지의 기존 예약 색상`, `발송 완료=complete`, `오류·기한 초과=danger` 의미를 유지한다.
- 카드의 클릭 동작은 실제 목록 필터 또는 이동과 연결한다. 목업 집계값을 실제 운영 집계처럼 표현하지 않는다.
- 값 `0`, `미확인`, `미연동`, `기록 없음`, `해당 없음`은 의미가 다르므로 구분한다.

## 8. 테이블·목록·필터

- 가능한 경우 검색창과 필터를 한 행에 배치한다.
- 시작일·종료일은 `.personal-content-date-range` 또는 `.newsletter-date-filter`처럼 하나의 `white-space: nowrap` 그룹으로 묶는다. 작은 화면에서는 기존 미디어 쿼리에 따라 줄바꿈하되 날짜 두 필드 사이가 분리되지 않게 한다.
- 목록의 핵심 정보부터 컬럼을 배치하고, 필요 없는 관리 컬럼을 추가하지 않는다.
- 상세 화면으로 이동하는 목록은 제목 또는 행 전체를 클릭 가능하게 하되, 행 안의 체크박스·버튼 클릭은 `stopPropagation` 등으로 구분한다.
- 기본 페이지 크기는 현재 주요 목록의 `20`을 유지하고, 필요한 화면에 한해 `10/20/50` 옵션을 제공한다.
- 검색·필터·페이지 크기 변경 시 페이지를 적절히 1페이지로 초기화한다.
- 긴 제목·이메일·추천 근거는 `min-width: 0`과 줄바꿈·말줄임을 조합한다.

## 9. 모달·스크롤·레이어

- 모달 배경은 `.modal-backdrop`의 `position: fixed; inset: 0`을 기준으로 전체 뷰포트를 덮는다.
- 헤더와 사이드바에 가려지지 않도록 Portal로 `document.body` 하위에 렌더링하고, 기존 레이어 순서를 따른다. 기본 모달은 `z-index: 1000`, 중첩 모달은 페이지별로 더 높은 레이어를 사용한다.
- 대형 목록·메일 작성 모달은 대체로 뷰포트의 `90vw/90vh` 이내이며, 모달 헤더와 푸터는 `flex: 0 0 auto`로 고정하고 중앙 콘텐츠만 `flex: 1; min-height: 0; overflow: auto`로 구성한다.
- 중첩 모달을 닫아도 부모 모달의 검색어, 필터, 페이지, 선택 및 스크롤 상태가 유지되도록 한다.
- Flex 자식이 스크롤되어야 하는 경우 부모와 자식에 `min-height: 0`, 필요한 경우 `min-width: 0`을 확인한다. 고정 높이를 무작정 늘리거나 글자를 줄여 문제를 숨기지 않는다.
- 테이블 헤더는 기존 `.recipient-table th`의 sticky 패턴처럼 스크롤 시 상단에 유지한다.
- 전역 스크롤바는 어두운 트랙과 손잡이를 사용한다. 페이지별로 흰색 기본 스크롤바를 되살리지 않는다.

## 10. 날짜·시간 및 입력 상태

- 날짜 필드 전체가 클릭 트리거여야 한다. 브라우저 기본 날짜 아이콘 클릭에만 의존하지 않는다.
- 날짜 선택기는 기존 `DatePicker`/`DateField`의 연도·월 이동, 날짜 선택 후 닫힘, 외부 클릭·Escape 닫힘, 다크 테마를 유지한다.
- 발송 관련 시간은 `Asia/Seoul` 기준으로 검증하고, 오전·오후 12시 변환을 포함해 기존 저장 형식과 호환한다.
- 입력 변경으로 메일 문안·예약·승인 상태가 영향을 받는 페이지는 기존 무효화 규칙을 유지한다.
- 저장되지 않은 입력을 행사 변경, 고객 이동, 모달 닫기에서 임의로 덮어쓰지 않는다.

## 11. 데이터·발송 표시 원칙

- 화면 데이터와 타입은 해당 페이지의 `lib/*-data.ts`에서 확인한다. 원본 데이터·가공 데이터·목업 어댑터를 혼동하지 않는다.
- 규칙형 추천과 실제 AI 결과를 구분하고, 근거 없는 고객 관심사·직무·기업 정보를 생성하지 않는다.
- 대상 독자 같은 내부 판단용 필드는 목록 표시에서 제외하더라도 상세 정보와 추천 로직에서 필요한 경우 보존한다.
- 실제 이메일, SMTP, 외부 API를 호출하지 않는다. 발송은 시뮬레이션·기록 상태로만 처리한다.
- 수신 동의, 유효 이메일, 중복 발송 방지, 담당자 승인 및 발송 완료 이력에 대한 기존 정책을 우회하지 않는다.
- 분석용 내부 문구, 개인정보, 고객 식별 정보가 외부 발송용 메일 본문에 노출되지 않도록 확인한다.

## 12. 신규 페이지 작업 순서 및 검증

1. 루트 [AGENTS.md](../AGENTS.md)와 이 문서를 읽는다.
2. 가장 유사한 기존 페이지와 실제 브라우저 화면을 확인한다.
3. 재사용 가능한 컴포넌트와 CSS 선택자를 확인한다.
4. 데이터 타입·상태 전환·라우팅을 확인한다.
5. 기존 토큰과 레이아웃을 사용해 구현한다.
6. 실제 브라우저에서 주요 화면, 필터, 페이지네이션, 모달, 스크롤, 날짜·시간 선택, 버튼 동작을 확인한다.
7. 다음 명령으로 코드 품질을 검증한다.

```powershell
Set-Location frontend
npx tsc --noEmit
npm run lint
npm run build
Set-Location ..
git -c safe.directory=D:/IeumLearning_PostEvent_AX diff --check
```

1920×1080, 1366×768, 브라우저 확대 125% 확인이 필요한 작업은 실제로 각 환경을 확인한 결과만 보고한다. 확인하지 못한 환경은 미검증으로 명시한다.

## 13. 현재 구현의 차이와 권장 사항

- 공통 토큰과 기본 버튼·모달·테이블 클래스는 [globals.css](./app/globals.css)에 모여 있으나, 메일·뉴스레터·개인 맞춤 콘텐츠의 세부 UI는 페이지 전용 클래스가 많다. 새 공통 클래스를 추가할 때 기존 페이지의 시각적 회귀를 확인한다.
- `SectionHeader`는 대시보드용 공통 컴포넌트이고, 메일 계열 번호형 섹션 헤더는 아직 각 페이지의 `CardTitle`/JSX 구조를 따른다. 새 페이지에서 번호형 헤더가 필요하면 기존 메일 페이지 구조를 먼저 재사용한다.
- `DatePicker`와 `DateField`는 공통 파일로 통합되어 있지 않으므로, 수정 전 두 구현의 동작 차이를 확인한다. 무분별한 복사보다 공통화가 안전한지 판단하고 범위를 기록한다.
- `recipient-table`, `pagination`, `search-input`은 CSS 공통 스타일을 공유하지만, 데이터·이벤트·컬럼 구조는 각 페이지에 있다. 공통 컴포넌트로 간주해 무조건 API를 변경하지 않는다.
- 현재 일부 컴포넌트는 JSX가 압축되어 있다. 가독성 개선이 필요해도 작업 범위를 벗어난 대규모 포맷 변경은 피하고, 기능 변경과 분리하여 검증한다.

이 문서는 현재 코드에서 확인한 규칙과 권장 사항을 구분하여 기록한다. 구현이 변경되면 관련 항목과 실제 파일 위치를 함께 갱신한다.
