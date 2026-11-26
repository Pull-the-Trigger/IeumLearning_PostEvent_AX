export type ThankYouStatus = "draft" | "review" | "scheduled" | "sent";
export type RecipientFilter = "all" | "included" | "excluded";
export type CustomerRequest = { id: string; text: string; source: "field" | "contact" | "survey"; recordedAt?: string; categories?: ("reply" | "material" | "sales")[] };
export type SurveyAnswerSummary = { q4?: string; q5?: string; q6?: string; q7?: string };

export type CustomerProfile = {
  id: string;
  name: string;
  company: string;
  title: string;
  email: string;
  attended: boolean;
  consent: "Y" | "N" | "UNKNOWN";
  attendanceCount: number;
  surveyResponded: boolean;
  preQuestion?: string;
  interactionMemo?: string;
  requests?: CustomerRequest[];
  surveyAnswers?: SurveyAnswerSummary;
};

export type ThankYouEvent = {
  id: string;
  name: string;
  eventDate: string;
  appliedCount: number;
  attendedCount: number;
  surveyCount: number;
  surveyIdentifiedCount: number;
  surveyAnonymousCount: number;
  materialsUrl: string;
  surveyUrl: string;
  status: ThankYouStatus;
  recipients: CustomerProfile[];
  addedRecipientIds: string[];
  excludedRecipientIds: string[];
  includeMaterials: boolean;
  includeSurvey: boolean;
  senderName?: string;
  subject: string;
  greeting: string;
  materialsParagraph: string;
  surveyParagraph: string;
  scheduledDate: string;
  scheduledTime: string;
  approved: boolean;
  history: { sentAt: string; count: number; result: string; simulated: boolean }[];
  lastApproval?: { approvedAt: string; scheduledAt: string; count: number };
};

const companyNames = ["동명화학", "신화솔루션", "한빛테크", "이음파트너스", "브릿지랩", "모노웍스", "오름컴퍼니", "세움금융"];
const titles = ["부장", "팀장", "전무", "책임", "매니저", "대표"];

function makeRecipients(eventId: string, count: number, surveyCount: number): CustomerProfile[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `${eventId}-person-${String(index + 1).padStart(2, "0")}`,
    name: `참석자 ${String(index + 1).padStart(2, "0")}`,
    company: companyNames[index % companyNames.length],
    title: titles[index % titles.length],
    email: `attendee${String(index + 1).padStart(2, "0")}@example.com`,
    attended: true,
    consent: index % 7 === 0 ? "N" : "Y",
    attendanceCount: 1 + (index % 3),
    surveyResponded: index < surveyCount,
    preQuestion: index % 6 === 0 ? "실무에 적용할 때 고려할 점이 궁금합니다." : undefined,
    interactionMemo: index % 11 === 0 ? "후속 자료 전달 예정" : undefined,
  }));
}

export const initialThankYouEvents: ThankYouEvent[] = [
  { id: "event-seoul-ceo", name: "CEO 인사이트 특강 · 서울", eventDate: "2026-11-20", appliedCount: 96, attendedCount: 80, surveyCount: 14, surveyIdentifiedCount: 12, surveyAnonymousCount: 2, materialsUrl: "https://example.com/materials/ceo-seoul", surveyUrl: "https://example.com/survey/ceo-seoul", status: "review", recipients: makeRecipients("event-seoul-ceo", 80, 14), addedRecipientIds: [], excludedRecipientIds: ["event-seoul-ceo-person-07", "event-seoul-ceo-person-21"], includeMaterials: true, includeSurvey: true, subject: "{{행사명}}에 참석해 주셔서 감사합니다", greeting: "{{이름}} {{호칭}}, 안녕하세요.\n\n{{행사명}}에 참석해 주셔서 감사합니다.\n\n귀한 시간을 내어 함께해 주신 점 깊이 감사드립니다.", materialsParagraph: "행사에서 소개한 발표자료를 아래 링크에서 확인하실 수 있습니다.\n\n{{발표자료링크}}", surveyParagraph: "더 유익한 행사를 준비할 수 있도록 만족도 조사에 참여해 주시면 감사하겠습니다.\n\n이미 응답하셨다면 넘어가셔도 됩니다.\n\n{{만족도조사링크}}", scheduledDate: "2026-11-21", scheduledTime: "09:00", approved: false, history: [] },
  { id: "event-hr-ai", name: "HR 담당자 AI 특강", eventDate: "2026-11-18", appliedCount: 54, attendedCount: 45, surveyCount: 8, surveyIdentifiedCount: 8, surveyAnonymousCount: 0, materialsUrl: "", surveyUrl: "https://example.com/survey/hr-ai", status: "draft", recipients: makeRecipients("event-hr-ai", 45, 8), addedRecipientIds: [], excludedRecipientIds: [], includeMaterials: false, includeSurvey: true, subject: "{{행사명}}에 참석해 주셔서 감사합니다", greeting: "{{이름}} {{호칭}}, 안녕하세요.\n\n{{행사명}}에 참석해 주셔서 감사합니다.\n\n귀한 시간을 내어 함께해 주신 점 깊이 감사드립니다.", materialsParagraph: "행사에서 소개한 발표자료를 아래 링크에서 확인하실 수 있습니다.\n\n{{발표자료링크}}", surveyParagraph: "더 유익한 행사를 준비할 수 있도록 만족도 조사에 참여해 주시면 감사하겠습니다.\n\n이미 응답하셨다면 넘어가셔도 됩니다.\n\n{{만족도조사링크}}", scheduledDate: "2026-11-19", scheduledTime: "09:00", approved: false, history: [] },
  { id: "event-builderthon", name: "AI 빌더톤 데모데이", eventDate: "2026-11-15", appliedCount: 26, attendedCount: 20, surveyCount: 4, surveyIdentifiedCount: 4, surveyAnonymousCount: 0, materialsUrl: "https://example.com/materials/builderthon", surveyUrl: "https://example.com/survey/builderthon", status: "sent", recipients: makeRecipients("event-builderthon", 20, 4), addedRecipientIds: [], excludedRecipientIds: [], includeMaterials: true, includeSurvey: true, subject: "{{행사명}}에 참석해 주셔서 감사합니다", greeting: "{{이름}} {{호칭}}, 안녕하세요.\n\n{{행사명}}에 참석해 주셔서 감사합니다.\n\n귀한 시간을 내어 함께해 주신 점 깊이 감사드립니다.", materialsParagraph: "행사에서 소개한 발표자료를 아래 링크에서 확인하실 수 있습니다.\n\n{{발표자료링크}}", surveyParagraph: "더 유익한 행사를 준비할 수 있도록 만족도 조사에 참여해 주시면 감사하겠습니다.\n\n이미 응답하셨다면 넘어가셔도 됩니다.\n\n{{만족도조사링크}}", scheduledDate: "2026-11-16", scheduledTime: "09:00", approved: true, history: [{ sentAt: "2026-11-16 09:00", count: 20, result: "성공 20건", simulated: true }] },
];

export function normalizeEmail(value: string) { return value.trim().toLowerCase(); }
export function isValidEmail(value: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(value)); }
export function isValidUrl(value: string) { try { const url = new URL(value); return url.protocol === "http:" || url.protocol === "https:"; } catch { return false; } }
export function getBaseRecipients(event: ThankYouEvent) { return event.recipients.filter((person) => person.attended && isValidEmail(person.email)); }
export function getFinalRecipients(event: ThankYouEvent) { return getBaseRecipients(event).filter((person) => !event.excludedRecipientIds.includes(person.id)).length + event.addedRecipientIds.length; }
export function getStatusLabel(status: ThankYouStatus) { return ({ draft: "작성 대기", review: "검토 대기", scheduled: "발송 예정", sent: "발송 완료" })[status]; }
export function getStatusTone(status: ThankYouStatus) { return ({ draft: "warning", review: "pending", scheduled: "pending", sent: "complete" })[status] as "warning" | "pending" | "complete"; }
export function getGreetingName(person: CustomerProfile) { return person.title ? person.title : "담당자"; }
export function renderTemplate(event: ThankYouEvent, person: CustomerProfile, includeSurvey: boolean) {
  const greeting = event.greeting.replaceAll("{{이름}}", person.name).replaceAll("{{호칭}}", getGreetingName(person)).replaceAll("{{행사명}}", event.name);
  const materials = event.includeMaterials && event.materialsUrl ? `\n\n${event.materialsParagraph.replaceAll("{{발표자료링크}}", event.materialsUrl)}` : "";
  const survey = includeSurvey && event.includeSurvey && event.surveyUrl ? `\n\n${event.surveyParagraph.replaceAll("{{만족도조사링크}}", event.surveyUrl)}` : "";
  return `${greeting}${materials}${survey}\n\n감사합니다.\n\n이음러닝 마케팅본부장 한서윤 드림`;
}
