import { getBaseRecipients, initialThankYouEvents, isValidEmail, normalizeEmail, type CustomerProfile, type ThankYouEvent } from "@/lib/thank-you-mail-data";

export const PERSONAL_MAIL_STORAGE_KEY = "ieum-learning-personal-mail-v1";

export const questionTypes = [
  ["Q01", "AI 활용 및 도입 사례"],
  ["Q02", "교육 과정 및 대상"],
  ["Q03", "보안 및 AI 활용 정책"],
  ["Q04", "성과 측정 및 평가"],
  ["Q05", "AI 도입 전략 및 로드맵"],
  ["Q06", "조직 운영"],
  ["Q07", "서비스 세부 사항"],
  ["Q08", "기타"],
] as const;

export type QuestionTypeId = (typeof questionTypes)[number][0];
export type PersonalMailStatus = "draft" | "review" | "sent";
export type AttachmentOrigin = "registered" | "local";

export type PersonalAttachment = { id: string; name: string; size: number; type: string; origin: AttachmentOrigin; url?: string };
export type PersonalMailHistory = { sentAt: string; mode: "개별 즉시" | "개별 예약" | "일괄 즉시" | "일괄 예약"; result: "성공" | "실패"; subject: string; attachments: string[]; body: string };
export type PersonalMailDraft = {
  eventId: string;
  customerId: string;
  status: PersonalMailStatus;
  reviewed: boolean;
  requiredReview: boolean;
  excluded: boolean;
  questionTypes: QuestionTypeId[];
  questions: string[];
  sender: string;
  subject: string;
  body: string;
  attachments: PersonalAttachment[];
  scheduledAt?: string;
  createdAt?: string;
  updatedAt?: string;
  sentAt?: string;
  history: PersonalMailHistory[];
  followUps: { reply: boolean; material: boolean; sales: boolean };
};

export type PersonalMailGoal = { businessDays: number; targetDate: string };
export type PersonalMailState = { drafts: Record<string, PersonalMailDraft>; goals: Record<string, PersonalMailGoal> };

export function getPersonalKey(eventId: string, customerId: string) { return `${eventId}:${customerId}`; }
export function getRecipients(event: ThankYouEvent) { return event.recipients.filter((person) => getBaseRecipients(event).some((base) => base.id === person.id) || event.addedRecipientIds.includes(person.id)); }
export function getQuestion(person: CustomerProfile) { return person.preQuestion?.trim() ? person.preQuestion.trim() : ""; }
export function getQuestionType(person: CustomerProfile): QuestionTypeId | null { return getQuestion(person) ? "Q01" : null; }

function addBusinessDays(dateValue: string, businessDays: number) {
  const date = new Date(`${dateValue}T12:00:00+09:00`);
  let remaining = Math.max(0, businessDays);
  while (remaining > 0) { date.setDate(date.getDate() + 1); if (date.getDay() !== 0 && date.getDay() !== 6) remaining -= 1; }
  return date.toISOString().slice(0, 10);
}

export function countBusinessDays(startValue: string, targetValue: string) {
  const start = new Date(`${startValue}T12:00:00+09:00`);
  const target = new Date(`${targetValue}T12:00:00+09:00`);
  if (target <= start) return 0;
  let count = 0;
  for (const date = new Date(start); date < target; date.setDate(date.getDate() + 1)) if (date.getDay() !== 0 && date.getDay() !== 6) count += 1;
  return count;
}

export { addBusinessDays };
export function getDefaultGoal(event: ThankYouEvent): PersonalMailGoal { return { businessDays: 3, targetDate: addBusinessDays(event.eventDate, 3) }; }
export function getDefaultBody(event: ThankYouEvent, person: CustomerProfile, question: string) {
  const questionLine = question ? `\n\n남겨주신 질문을 확인했습니다.\n\n“${question}”\n\n관련 답변은 담당자 확인 후 안내드리겠습니다.` : "";
  const followUpLine = person.consent === "Y" ? "\n\n추가로 도움이 될 만한 자료가 준비되면 안내드리겠습니다." : "";
  return `${person.name} ${person.title || "담당자"}님, 안녕하세요.\n\n${event.name}에 참석해 주셔서 감사합니다.${questionLine}${followUpLine}\n\n감사합니다.\n\n이음러닝 마케팅본부장 한서윤 드림`;
}

export function createDraft(event: ThankYouEvent, person: CustomerProfile, index: number): PersonalMailDraft {
  const question = getQuestion(person);
  const type = getQuestionType(person);
  const requiredReview = Boolean(question) || person.consent === "N";
  const status: PersonalMailStatus = index % 7 === 0 ? "sent" : index % 3 === 0 ? "review" : "draft";
  const sentAt = status === "sent" ? `${event.eventDate} 17:00` : undefined;
  const history = sentAt ? [{ sentAt, mode: "개별 즉시" as const, result: "성공" as const, subject: `${event.name} 후속 안내`, attachments: [], body: getDefaultBody(event, person, question) }] : [];
  return { eventId: event.id, customerId: person.id, status, reviewed: status !== "draft", requiredReview, excluded: false, questionTypes: type ? [type] : [], questions: question ? [question] : [], sender: "이음러닝 마케팅본부장 한서윤", subject: `${event.name} 관련 후속 안내`, body: getDefaultBody(event, person, question), attachments: [], sentAt, history, followUps: { reply: Boolean(question), material: false, sales: person.consent === "Y" && person.title === "대표" } };
}

export function createInitialPersonalState(events = initialThankYouEvents): PersonalMailState {
  const drafts: Record<string, PersonalMailDraft> = {};
  const goals: Record<string, PersonalMailGoal> = {};
  events.forEach((event) => { goals[event.id] = getDefaultGoal(event); getRecipients(event).forEach((person, index) => { drafts[getPersonalKey(event.id, person.id)] = createDraft(event, person, index); }); });
  return { drafts, goals };
}

export function readPersonalState(events = initialThankYouEvents): PersonalMailState {
  if (typeof window === "undefined") return createInitialPersonalState(events);
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PERSONAL_MAIL_STORAGE_KEY) || "null") as PersonalMailState | null;
    return parsed?.drafts && parsed.goals ? parsed : createInitialPersonalState(events);
  } catch { return createInitialPersonalState(events); }
}

export function isSendable(person: CustomerProfile, draft: PersonalMailDraft) { return isValidEmail(person.email) && Boolean(draft.subject.trim()) && Boolean(draft.body.trim()) && !draft.excluded && draft.status !== "sent"; }
export function normalizePersonEmail(person: CustomerProfile) { return normalizeEmail(person.email); }
