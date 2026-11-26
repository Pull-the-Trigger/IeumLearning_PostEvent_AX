import { initialThankYouEvents, isValidEmail, normalizeEmail, type CustomerProfile } from "@/lib/thank-you-mail-data";

export type NewsletterStatus = "draft" | "review" | "scheduled" | "sent";
export type AudienceMode = "all-consent" | "conditions";
export type NewsletterAudience = {
  mode: AudienceMode;
  roles: string[];
  industries: string[];
  companySizes: string[];
  interests: string[];
};
export type Publication = { id: string; publishedAt: string; channel: string; title: string; topic: string; audience: string; link: string };
export type NewsletterAttachment = { id: string; name: string; size?: number; source: "등록 자료" | "직접 첨부" };
export type NewsletterLink = { id: string; title: string; url: string; kind: string; intro: string };
export type NewsletterRecord = {
  id: string; title: string; purpose: string; issue: string; createdAt: string; updatedAt: string;
  status: NewsletterStatus; audience: NewsletterAudience; publicationIds: string[]; customLinks: NewsletterLink[]; intro: string;
  eventId?: string; sender: string; subject: string; body: string; attachments: NewsletterAttachment[];
  scheduledDate?: string; scheduledTime?: string; sentAt?: string; history: string[]; historical?: boolean;
};

export const newsletterRoles = ["경영진", "HR", "교육", "DX·AX", "IT", "개발", "현업", "기타(미확인)"];
export const newsletterIndustries = ["제조", "IT·소프트웨어", "금융·보험", "유통·커머스", "교육", "전문서비스·컨설팅", "의료·바이오", "건설·부동산", "공공·비영리", "미디어·콘텐츠", "물류·운송", "기타", "미확인"];
export const newsletterCompanySizes = ["대기업", "중견기업", "중소기업", "스타트업", "기타(미확인)"];
export const newsletterInterests = ["Q01 AI 활용 및 도입 사례", "Q02 교육 과정 및 대상", "Q03 보안 및 AI 활용 정책", "Q04 성과 측정 및 평가", "Q05 AI 도입 전략 및 로드맵", "Q06 조직 운영", "Q07 서비스 세부 사항", "Q08 기타", "관심사 미확인"];

const publicationRows: [string, string, string, string, string, string][] = [
  ["2026-07-05", "비개발 직군 교육에서 중도 이탈이 생기는 구간", "직무별 AI 교육 과정", "교육 담당자", "blog", "260705-01"],
  ["2026-07-06", "HR 담당자 특강에서 가장 많이 나온 고민", "행사 후기", "HR 담당자", "blog", "260706-02"],
  ["2026-07-11", "7월 CEO 인사이트 특강에서 나온 질문 정리", "행사 후기", "경영진", "social", "260711-03"],
  ["2026-07-14", "대표가 직접 챙겨야 하는 결정 세 가지", "AI 전환 로드맵", "경영진", "blog", "260714-04"],
  ["2026-07-15", "작은 회사가 AI 도입을 시작할 때 정해야 할 것", "AI 도입 우선순위", "경영진", "social", "260715-05"],
  ["2026-07-16", "자동화 과제를 고르는 점수표", "현업 부서 자동화", "DX 담당자", "blog", "260716-06"],
  ["2026-07-21", "규정을 만들고도 지켜지지 않는 경우", "생성형 AI 보안·규정", "DX 담당자", "social", "260721-07"],
  ["2026-07-23", "현업이 만든 자동화가 석 달 뒤에 멈추는 이유", "현업 부서 자동화", "DX 담당자", "blog", "260723-08"],
  ["2026-07-24", "주간 보고서 작성 시간을 줄인 재무팀 사례", "현업 부서 자동화", "현업 팀장", "blog", "260724-09"],
  ["2026-07-25", "예산 3천만 원으로 시작한 중견기업의 1년", "AI 도입 우선순위", "경영진", "blog", "260725-10"],
  ["2026-07-26", "만족도 점수가 높아도 성과가 없는 교육", "교육 효과 측정", "교육 담당자", "blog", "260726-11"],
  ["2026-07-27", "1년 계획을 분기별로 나누는 방법", "AI 전환 로드맵", "경영진", "blog", "260727-12"],
  ["2026-07-30", "AI를 쓰게 한 코딩 테스트에서 무엇을 평가하는가", "개발자 채용 평가", "개발팀장", "blog", "260730-13"],
  ["2026-07-31", "교육 전후 차이를 숫자로 보여 주는 방법", "교육 효과 측정", "교육 담당자", "blog", "260731-14"],
  ["2026-08-01", "부서별 AI 활용 수준을 비교하는 세 가지 기준", "임직원 AI 역량 진단", "HR 담당자", "blog", "260801-15"],
  ["2026-08-03", "경력직 과제 전형을 다시 설계한 과정", "개발자 채용 평가", "개발팀장", "blog", "260803-16"],
  ["2026-08-06", "부산 특강 현장의 질의응답", "행사 후기", "경영진", "blog", "260806-17"],
  ["2026-08-09", "빌더톤 참가팀이 만든 결과물 다섯 가지", "행사 후기", "개발팀장", "social", "260809-18"],
  ["2026-08-11", "전담 조직 없이 시작한 회사의 역할 분담", "AI 전환 로드맵", "경영진", "blog", "260811-19"],
  ["2026-08-12", "면접관마다 다른 평가를 맞추는 기록 방법", "개발자 채용 평가", "HR 담당자", "blog", "260812-20"],
  ["2026-08-16", "부서장 인터뷰에서 꼭 물어야 할 질문", "AI 도입 우선순위", "DX 담당자", "blog", "260816-21"],
  ["2026-08-20", "외부 도구 사용 신청 절차의 예", "생성형 AI 보안·규정", "IT 담당자", "blog", "260820-22"],
  ["2026-08-23", "생산기술팀이 직접 만든 점검표 자동화", "직무별 AI 교육 과정", "현업 팀장", "blog", "260823-23"],
  ["2026-08-24", "전 직원 진단을 2주 안에 끝낸 제조 기업 사례", "임직원 AI 역량 진단", "경영진", "blog", "260824-24"],
  ["2026-08-25", "부서별 담당자를 정할 때의 기준", "AI 전환 로드맵", "DX 담당자", "blog", "260825-25"],
  ["2026-08-26", "경영진 보고에 넣는 지표 네 가지", "교육 효과 측정", "HR 담당자", "blog", "260826-26"],
  ["2026-09-02", "진단 문항은 어떻게 만들어지는가", "임직원 AI 역량 진단", "교육 담당자", "blog", "260902-27"],
  ["2026-09-04", "교육 시간을 업무 시간 안에 넣는 편성 방법", "직무별 AI 교육 과정", "HR 담당자", "blog", "260904-28"],
  ["2026-09-11", "고객 문의 분류를 자동화할 때의 검수 절차", "현업 부서 자동화", "현업 팀장", "blog", "260911-29"],
  ["2026-09-15", "사용 규정 초안을 한 달 안에 만든 과정", "생성형 AI 보안·규정", "경영진", "blog", "260915-30"],
  ["2026-09-17", "진단 결과를 받은 뒤에 인사팀이 가장 먼저 하는 일", "임직원 AI 역량 진단", "HR 담당자", "blog", "260917-31"],
  ["2026-09-19", "사내 자료를 AI에 넣어도 되는지 정하는 기준", "생성형 AI 보안·규정", "DX 담당자", "blog", "260919-32"],
  ["2026-09-21", "신입 개발자 평가 문항의 난이도 조정", "개발자 채용 평가", "개발팀장", "blog", "260921-33"],
  ["2026-09-24", "영업 조직이 AI 교육에서 실제로 쓴 실습 과제", "직무별 AI 교육 과정", "현업 팀장", "blog", "260924-34"],
  ["2026-09-26", "첫 과제로 고르면 안 되는 업무의 특징", "AI 도입 우선순위", "경영진", "blog", "260926-35"],
  ["2026-09-28", "6개월 뒤에 다시 진단해서 확인한 것", "교육 효과 측정", "HR 담당자", "blog", "260928-36"],
];
export const publicationCatalog: Publication[] = publicationRows.map(([publishedAt, title, topic, audience, channel, suffix], index) => ({ id: `publication-${index + 1}`, publishedAt, channel: channel === "blog" ? "블로그" : "링크드인", title, topic, audience, link: channel === "blog" ? `https://blog.ieumlearning.example/posts/${suffix}` : `https://social.example/ieumlearning/post/${suffix}` }));

const baseAudience = (): NewsletterAudience => ({ mode: "all-consent", roles: [], industries: [], companySizes: [], interests: [] });
export const newsletterStorageKey = "ieum-learning-newsletters-v1";
export const initialNewsletters: NewsletterRecord[] = [
  { id: "newsletter-history-may", title: "2026년 5월호: 진단 결과를 받은 뒤에 인사팀이 가장 먼저 하는 일", purpose: "과거 발송 문안", issue: "2026년 5월호", createdAt: "미확인", updatedAt: "미확인", status: "sent", audience: baseAudience(), publicationIds: [], customLinks: [], intro: "과거 발송 문안에서 확인된 뉴스레터입니다.", sender: "이음러닝 마케팅본부장 한서윤", subject: "2026년 5월호", body: "원문 발송 이력은 참고 문서에서 확인하세요.", attachments: [], history: [], historical: true },
  { id: "newsletter-history-june", title: "2026년 6월호: 작은 회사가 AI 도입을 시작할 때 정해야 할 것", purpose: "과거 발송 문안", issue: "2026년 6월호", createdAt: "미확인", updatedAt: "미확인", status: "sent", audience: baseAudience(), publicationIds: [], customLinks: [], intro: "과거 발송 문안에서 확인된 뉴스레터입니다.", sender: "이음러닝 마케팅본부장 한서윤", subject: "2026년 6월호", body: "원문 발송 이력은 참고 문서에서 확인하세요.", attachments: [], history: [], historical: true },
  { id: "newsletter-draft-demo", title: "", purpose: "", issue: "", createdAt: "2026-11-26", updatedAt: "2026-11-26", status: "draft", audience: baseAudience(), publicationIds: [], customLinks: [], intro: "", sender: "이음러닝 마케팅본부장 한서윤", subject: "", body: "", attachments: [], history: [] },
];

export function getNewsletterProfiles(): CustomerProfile[] {
  const map = new Map<string, CustomerProfile>();
  initialThankYouEvents.flatMap((event) => event.recipients).forEach((person) => { const email = normalizeEmail(person.email); if (isValidEmail(email) && person.consent === "Y" && !map.has(email)) map.set(email, person); });
  return [...map.values()];
}
