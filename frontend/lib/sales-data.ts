import type { Inquiry } from "@/lib/request-data";

export type SalesType = "S01" | "S02" | "S03" | "S04" | "S05" | "S06";
export type SalesStatus = "review" | "transferred" | "excluded";
export type SalesEvidence = { id: string; type: SalesType; source: string; text: string; occurredAt?: string };
export type SalesCandidate = {
  id: string; inquiryId: string; customerId: string; name: string; company: string; title: string; email: string;
  eventName?: string; types: SalesType[]; status: SalesStatus; latestInquiryAt?: string; summary: string;
  evidence: SalesEvidence[]; registrationSource: string; extraNote?: string; transferredAt?: string; excludedAt?: string; exclusionReason?: string;
};

export const salesTypeLabels: Record<SalesType, string> = {
  S01: "연락 희망", S02: "도입 검토", S03: "구체적 도입 문의", S04: "서비스 자료 요청", S05: "상담·미팅 요청", S06: "견적 요청",
};
export const salesStatusLabels: Record<SalesStatus, string> = { review: "검토 대기", transferred: "전달 완료", excluded: "전달 제외" };

const typeForInquiry = (inquiry: Inquiry): SalesType[] => {
  const text = `${inquiry.inquiryTitle} ${inquiry.initialText} ${inquiry.currentText} ${inquiry.messages.map((m) => m.body).join(" ")}`;
  const types: SalesType[] = [];
  if (inquiry.email && /상담|연락|담당자|미팅/.test(text)) types.push(/미팅|상담/.test(text) ? "S05" : "S01");
  if (/도입|예산|검토|교육을 진행|진단을/.test(text)) types.push("S02");
  if (/소개서|자료|과정|제공 범위/.test(text) && !types.includes("S04")) types.push("S04");
  if (/견적|금액|비용/.test(text)) types.push(/견적/.test(text) ? "S06" : "S03");
  if (/직원|대상|규모|운영|적용/.test(text) && !types.includes("S03")) types.push("S03");
  return types;
};

const latestCustomerContact = (inquiry: Inquiry): string | undefined => {
  const customerMessages = inquiry.messages.filter((message) => message.direction !== "internal");
  return customerMessages.map((message) => message.sentAt.slice(0, 10)).sort().at(-1) || inquiry.firstContactAt || inquiry.lastContactAt;
};

const reasonForInquiry = (inquiry: Inquiry, types: SalesType[]): string => {
  const sourceText = inquiry.messages.find((message) => message.direction === "inbound")?.body || inquiry.initialText || inquiry.inquiryTitle;
  const typeText = types.map((type) => salesTypeLabels[type]).join(", ");
  return `고객이 "${sourceText}"라고 문의했으며 ${typeText} 관련 관심과 확인 요청이 기록되었습니다. 영업팀에서 고객의 요구사항과 후속 상담 가능성을 검토할 수 있습니다.`;
};

export function buildSalesCandidates(inquiries: Inquiry[]): SalesCandidate[] {
  return inquiries.flatMap((inquiry) => {
    const types = typeForInquiry(inquiry);
    if (!types.length) return [];
    const latestInquiryAt = latestCustomerContact(inquiry);
    const evidence = types.map((type, index) => ({ id: `${inquiry.id}-evidence-${index}`, type, source: inquiry.source, text: inquiry.messages.find((message) => message.direction === "inbound")?.body || inquiry.initialText, occurredAt: latestInquiryAt }));
    return [{ id: `sales-${inquiry.id}`, inquiryId: inquiry.id, customerId: inquiry.customerId, name: inquiry.name, company: inquiry.company, title: inquiry.title, email: inquiry.email, eventName: inquiry.eventName, types, status: "review", latestInquiryAt, summary: reasonForInquiry(inquiry, types), registrationSource: "고객 문의 자동 분석", evidence }];
  });
}
