export type SurveyQuestionType = "scale" | "score" | "textarea" | "choice" | "email";

export type SurveyQuestion = {
  id: `Q${number}`;
  text: string;
  responseFormat: string;
  type: SurveyQuestionType;
  options?: string[];
  required: boolean;
};

export type SurveyDefinition = {
  eventId: string;
  eventName: string;
  surveyId: string;
  templateId: string;
  token: string;
  status: "open" | "closed";
};

export type SurveyResponse = {
  responseId: string;
  eventId: string;
  surveyId: string;
  submittedAt: string;
  answers: Record<string, string>;
  email?: string;
  customerLinkKey?: string;
  identified: boolean;
  contactFollowUp: boolean;
};

export const surveyTemplate = {
  id: "common-satisfaction-v1",
  questions: [
    { id: "Q1", text: "행사에 전반적으로 만족하셨습니까?", responseFormat: "5점 척도", type: "scale", options: ["1", "2", "3", "4", "5"], required: true },
    { id: "Q2", text: "내용이 업무에 도움이 되었습니까?", responseFormat: "5점 척도", type: "scale", options: ["1", "2", "3", "4", "5"], required: true },
    { id: "Q3", text: "동료에게 이 행사를 추천하시겠습니까?", responseFormat: "0~10점", type: "score", options: ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], required: true },
    { id: "Q4", text: "가장 도움이 된 내용은 무엇입니까?", responseFormat: "서술", type: "textarea", required: true },
    { id: "Q5", text: "다음에 듣고 싶은 주제는 무엇입니까?", responseFormat: "서술", type: "textarea", required: true },
    { id: "Q6", text: "사내 AI 교육이나 진단 도입을 검토하고 계십니까?", responseFormat: "예 / 검토 중 / 아니오", type: "choice", options: ["예", "검토 중", "아니오"], required: true },
    { id: "Q7", text: "담당자의 연락을 원하십니까?", responseFormat: "예 / 아니오", type: "choice", options: ["예", "아니오"], required: true },
    { id: "Q8", text: "이메일 (선택)", responseFormat: "서술", type: "email", required: false },
  ] satisfies SurveyQuestion[],
} as const;

export const surveyDefinitions: SurveyDefinition[] = [
  { eventId: "event-seoul-ceo", eventName: "CEO 인사이트 특강 · 서울", surveyId: "survey-event-seoul-ceo-v1", templateId: surveyTemplate.id, token: "e01-ceo-seoul-7f4c2a91", status: "open" },
  { eventId: "event-hr-ai", eventName: "HR 담당자 AI 특강", surveyId: "survey-event-hr-ai-v1", templateId: surveyTemplate.id, token: "e02-hr-ai-3b8d6e52", status: "open" },
  { eventId: "event-builderthon", eventName: "AI 빌더톤 데모데이", surveyId: "survey-event-builderthon-v1", templateId: surveyTemplate.id, token: "e03-builderthon-9a1e5c73", status: "open" },
];

export const SURVEY_RESPONSE_STORAGE_KEY = "ieum-learning-survey-responses-v1";
export const LEGACY_SURVEY_RESPONSE_COUNT = 45;

export function getSurveyDefinitionByToken(token: string) {
  return surveyDefinitions.find((item) => item.token === token);
}

export function getSurveyDefinitionForEvent(eventId: string) {
  return surveyDefinitions.find((item) => item.eventId === eventId);
}

export function getSurveyPath(token: string, preview = false) {
  return preview ? `/survey/preview/${token}` : `/survey/${token}`;
}

export function getPublicSurveyUrl(definition: SurveyDefinition, preview = false) {
  const path = getSurveyPath(definition.token, preview);
  const configuredOrigin = process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "");
  if (typeof window !== "undefined") return `${window.location.origin}${path}`;
  return configuredOrigin ? `${configuredOrigin}${path}` : path;
}

export function getPublicSurveyUrlForEvent(eventId: string, preview = false) {
  const definition = getSurveyDefinitionForEvent(eventId);
  return definition ? getPublicSurveyUrl(definition, preview) : "";
}

export function normalizeSurveyEmail(value: string) {
  return value.trim().toLowerCase();
}

export function readSurveyResponses(): SurveyResponse[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SURVEY_RESPONSE_STORAGE_KEY);
    return raw ? JSON.parse(raw) as SurveyResponse[] : [];
  } catch {
    return [];
  }
}

export function saveSurveyResponse(response: SurveyResponse) {
  if (typeof window === "undefined") return;
  const responses = readSurveyResponses();
  window.localStorage.setItem(SURVEY_RESPONSE_STORAGE_KEY, JSON.stringify([...responses, response]));
}
