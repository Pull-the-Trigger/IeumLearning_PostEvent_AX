import { apiGet } from "@/lib/api";
import type { CustomerProfile } from "@/lib/thank-you-mail-data";
import type { SurveyResponse } from "@/lib/survey-data";

export type DataManagementKind = "events" | "people" | "content";
export type DataTab = "customers" | "participation" | "surveys" | "interactions";

export type EventRow = { eventId: string; eventName: string; eventDate: string; eventType: string; appliedCount: number; attendedCount: number; thanksMailDate: string; surveyCount: number; note: string; thanksGoalDate: string; personalGoalDate: string; thanksGoalMode: "자동 산정" | "수동 변경"; personalGoalMode: "자동 산정" | "수동 변경"; personalMailStatus: string };
export type CustomerRow = CustomerProfile & { industry: string; existingCustomer: string; firstEventId: string; lastEventId: string; appliedCount: number; attendedCount: number; interests: string };
export type ParticipationRow = CustomerProfile & { eventId: string; eventName: string; preQuestion: string; note: string };
export type SurveyRow = Omit<SurveyResponse, "surveyId" | "submittedAt"> & { eventName: string; responseDate: string; linkedState: string };
export type InteractionRow = { id: string; eventId: string; eventName: string; name: string; company: string; email: string; contactDate: string; method: string; memo: string; result: string };
export type ContentRow = { contentId: string; publishedDate: string; channel: string; title: string; topic: string; audience: string; url: string };

type EventBase = Omit<EventRow, "thanksGoalDate" | "personalGoalDate" | "thanksGoalMode" | "personalGoalMode" | "personalMailStatus">;

function addDays(value: string, days: number) { const date = new Date(`${value}T12:00:00`); date.setDate(date.getDate() + days); return date.toISOString().slice(0, 10); }
function addBusinessDays(value: string, days: number) { const date = new Date(`${value}T12:00:00`); let remaining = days; while (remaining > 0) { date.setDate(date.getDate() + 1); if (date.getDay() !== 0 && date.getDay() !== 6) remaining -= 1; } return date.toISOString().slice(0, 10); }
function withGoals(row: EventBase): EventRow { return { ...row, thanksGoalDate: addDays(row.eventDate, 1), personalGoalDate: addBusinessDays(row.eventDate, 3), thanksGoalMode: "자동 산정", personalGoalMode: "자동 산정", personalMailStatus: "미연동" }; }

export { addBusinessDays, addDays };

export async function getEventRows(): Promise<EventRow[]> { return (await apiGet<EventBase[]>("/events")).map(withGoals); }
export function getCustomerRows() { return apiGet<CustomerRow[]>("/customers"); }
export function getParticipationRows() { return apiGet<ParticipationRow[]>("/participation"); }
export function getSurveyRows() { return apiGet<SurveyRow[]>("/surveys"); }
export function getInteractionRows() { return apiGet<InteractionRow[]>("/interactions"); }
export function getContentRows() { return apiGet<ContentRow[]>("/contents"); }

export const uploadSchemas = {
  events: { label: "행사 목록", files: ["00_행사목록_2026년3분기.xlsx"], columns: [{ name: "행사 ID", required: true, aliases: ["행사 ID"] }, { name: "행사명", required: true, aliases: ["행사명"] }, { name: "개최일", required: true, aliases: ["개최일"] }, { name: "유형", required: false, aliases: ["유형"] }, { name: "신청 인원", required: false, aliases: ["신청 인원"] }, { name: "참석 인원", required: false, aliases: ["참석 인원"] }, { name: "감사 메일 발송일", required: false, aliases: ["감사 메일 발송일"] }, { name: "설문 응답 수", required: false, aliases: ["설문 응답 수"] }, { name: "비고", required: false, aliases: ["비고"] }] },
  participation: { label: "참가자 명단", files: ["01_참가자명단_E0X_*.xlsx"], columns: [{ name: "이름", required: true, aliases: ["이름", "성함", "성명", "신청자명", "참가자명"] }, { name: "회사", required: false, aliases: ["회사", "소속", "회사명"] }, { name: "직함", required: false, aliases: ["직함", "직책", "직급", "직급/직책", "직 급"] }, { name: "이메일", required: true, aliases: ["이메일", "메일 주소", "E-mail", "메일주소"] }, { name: "사전 질문", required: false, aliases: ["사전 질문", "궁금한 점", "질문사항", "사전질문"] }, { name: "참석", required: true, aliases: ["참석", "출석여부", "출석", "참석 체크"] }, { name: "마케팅 수신 동의", required: false, aliases: ["마케팅 수신 동의", "뉴스레터 수신", "수신동의 여부", "이메일 수신 동의"] }, { name: "비고", required: false, aliases: ["비고", "메모"] }] },
  surveys: { label: "만족도 설문", files: ["02_만족도설문_문항과응답.xlsx"], columns: [{ name: "행사 ID", required: true, aliases: ["행사 ID"] }, { name: "응답일", required: false, aliases: ["응답일"] }, { name: "Q1~Q8", required: false, aliases: ["Q1 만족도", "Q2 도움 정도", "Q3 추천 의향", "Q4 도움이 된 내용", "Q5 듣고 싶은 주제", "Q6 도입 검토", "Q7 연락 희망", "Q8 이메일"] }] },
  interactions: { label: "후속 연락 기록", files: ["04_후속연락기록_담당자메모.xlsx"], columns: [{ name: "행사 ID", required: true, aliases: ["행사 ID"] }, { name: "이름", required: false, aliases: ["이름"] }, { name: "회사", required: false, aliases: ["회사"] }, { name: "연락일", required: false, aliases: ["연락일"] }, { name: "방법", required: false, aliases: ["방법"] }, { name: "메모", required: false, aliases: ["메모"] }, { name: "결과", required: false, aliases: ["결과"] }] },
  contents: { label: "발행 콘텐츠", files: ["03_발행글목록_2026년3분기.xlsx"], columns: [{ name: "번호", required: true, aliases: ["번호"] }, { name: "발행일", required: true, aliases: ["발행일"] }, { name: "채널", required: false, aliases: ["채널"] }, { name: "제목", required: true, aliases: ["제목"] }, { name: "주제", required: false, aliases: ["주제"] }, { name: "대상 독자", required: false, aliases: ["대상 독자"] }, { name: "링크", required: false, aliases: ["링크"] }] },
} as const;

export function getDataTitle(kind: DataManagementKind) { return kind === "events" ? "행사 정보" : kind === "people" ? "참가자 및 고객 정보" : "콘텐츠 및 자료"; }
