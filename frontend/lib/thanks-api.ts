/** 감사 메일 승인 API (/thanks) 호출 함수와 타입. 응답 형식은 backend/app/thanks.py 기준. */
import { apiGet, apiPost } from "@/lib/api";

export type ThanksStatus = "draft" | "review" | "scheduled" | "sent";
export type ThanksApprovalStatus = "none" | "scheduled" | "sent" | "excluded";

/** GET /thanks 한 행. 값이 없으면 키가 빠짐 (sendBy, sendByPassed, scheduledAt, sentAt). */
export type ThanksSummary = {
  eventId: string;
  eventName: string;
  eventDate: string;
  draftCount: number;
  excludedCount: number;
  status: ThanksStatus;
  sendBy?: string;
  sendByPassed?: boolean;
  scheduledAt?: string;
  sentAt?: string;
};

export type ThanksRecipient = {
  draftId: string;
  email: string;
  name: string;
  company: string;
  title: string;
  subject: string;
  body: string;
  sender: string;
  surveyIncluded: boolean;
  approvalStatus: ThanksApprovalStatus;
  approvalInvalid: boolean;
};

export type ThanksDetail = ThanksSummary & { recipients: ThanksRecipient[] };

export type ThanksApproveBody = { mode: "now" | "scheduled"; scheduledAt?: string; excludedEmails: string[] };
export type ThanksApproveResult = ThanksSummary & { warnings: string[] };

export type HealthInfo = { status: string; db: string; today: string; demo: boolean };

/** 행사별 감사 메일 문안·링크 (POST /thanks/{id}/template 본문과 같은 필드). */
export type ThanksTemplateInput = { subjectTemplate: string; bodyTemplate: string; surveyAskBlock: string; slidesUrl: string; surveyUrl: string };
export type ThanksTemplateField = keyof ThanksTemplateInput;

/** GET /thanks/{id}/template. customized=false 면 template.txt + config.json 기본값. */
export type ThanksTemplate = ThanksTemplateInput & {
  eventId: string;
  customized: boolean;
  updatedAt?: string;
  placeholders: { subjectTemplate: string[]; bodyTemplate: string[]; surveyAskBlock: string[] };
  fixed: { surveyThanksBlock: string; signature: string };
};

/** 저장·되돌리기 응답: 저장 후 문안 + 행사 상태, 이번에 무효가 된 승인 수, 글쓰기 기준 경고. */
export type ThanksTemplateSaveResult = ThanksTemplate & { status: ThanksStatus; invalidatedCount: number; warnings: string[] };

const eventPath = (eventId: string) => `/thanks/${encodeURIComponent(eventId)}`;

export function getThanksList() { return apiGet<ThanksSummary[]>("/thanks"); }
export function getThanksDetail(eventId: string) { return apiGet<ThanksDetail>(eventPath(eventId)); }
export function approveThanks(eventId: string, body: ThanksApproveBody) { return apiPost<ThanksApproveResult>(`${eventPath(eventId)}/approve`, body); }
export function cancelThanks(eventId: string) { return apiPost<ThanksSummary>(`${eventPath(eventId)}/cancel`); }
export function getHealth() { return apiGet<HealthInfo>("/health"); }
export function getThanksTemplate(eventId: string) { return apiGet<ThanksTemplate>(`${eventPath(eventId)}/template`); }
export function saveThanksTemplate(eventId: string, body: ThanksTemplateInput) { return apiPost<ThanksTemplateSaveResult>(`${eventPath(eventId)}/template`, body); }
export function resetThanksTemplate(eventId: string) { return apiPost<ThanksTemplateSaveResult>(`${eventPath(eventId)}/template/reset`); }
export function templateInput(t: ThanksTemplateInput): ThanksTemplateInput { return { subjectTemplate: t.subjectTemplate, bodyTemplate: t.bodyTemplate, surveyAskBlock: t.surveyAskBlock, slidesUrl: t.slidesUrl, surveyUrl: t.surveyUrl }; }

/** 'YYYY-MM-DD' 다음 날 (브라우저 날짜·시간대와 무관하게 문자열 기준으로 계산). */
export function nextDay(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}
