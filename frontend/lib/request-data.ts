export type InquiryStatus = "answer_pending" | "collaboration" | "review" | "completed";
export type CollaborationStatus = "request_pending" | "reply_pending" | "confirmed";
export type InquirySource = "사전 질문" | "현장 질문" | "현장 자료 요청" | "만족도 설문" | "감사 메일 회신" | "개인 맞춤 메일 회신" | "뉴스레터 회신" | "개인 맞춤 콘텐츠 회신" | "문의 답변 메일 회신" | "전화" | "메신저" | "대면";
export type ContactChannel = "이메일" | "전화" | "메신저" | "대면";
export type RequestType = "질문 답변" | "자료 전달" | "영업 관련 요청";

export type RequestAttachment = { id: string; name: string; size?: number; source: "등록 자료" | "직접 첨부"; url?: string };
export type InquiryMessage = { id: string; sentAt: string; direction: "inbound" | "outbound" | "internal"; channel: ContactChannel | "내부 메모"; sender: string; body: string; subject?: string; attachments?: RequestAttachment[]; links?: string[] };
export type InquiryRequest = { id: string; type: RequestType; text: string; status: "pending" | "in_progress" | "completed"; result?: string };
export type InquiryDraft = { sender: string; subject: string; body: string; attachments: RequestAttachment[]; reviewed: boolean };
export type InquiryActivity = { id: string; date: string; type: string; title: string; detail?: string };
export type InquiryProfile = {
  roleClassification?: string;
  industry?: string;
  companySize?: string;
  existingCustomer?: "예" | "아니오" | "미확인";
  marketingConsent?: "동의" | "미동의" | "미확인";
  firstEventDate?: string;
  lastEventDate?: string;
  appliedCount?: number;
  attendedCount?: number;
  surveyResponseCount?: number;
  interests?: string[];
  interestEvidence?: string[];
  activity?: InquiryActivity[];
};
export type CollaborationRecord = { id: string; department: string; direction: "outbound" | "inbound"; kind: "협업 요청" | "부서 회신" | "추가 확인 요청"; occurredAt: string; channel?: ContactChannel | "내부 기록"; body: string; attachments?: RequestAttachment[]; memo?: string };
export type Inquiry = {
  id: string; customerId: string; name: string; company: string; title: string; email: string;
  inquiryTitle: string; source: InquirySource; currentChannel: ContactChannel; initialText: string; currentText: string;
  eventName?: string; contentTitle?: string; sentMailSubject?: string; firstContactAt: string; lastContactAt: string;
  types: RequestType[]; departments: string[]; status: InquiryStatus; messages: InquiryMessage[]; requests: InquiryRequest[]; memo?: string; draft?: InquiryDraft;
  profile?: InquiryProfile; initialOriginalText?: string; initialOriginalKind?: InquirySource;
};
export type CollaborationProgress = { id: string; date: string; department: string; status: string; note: string };
export type CollaborationTask = {
  id: string; inquiryId: string; customerId: string; name: string; company: string; title: string;
  departments: string[]; registeredAt: string; dueDate?: string; updatedAt: string; status: CollaborationStatus;
  requestBody: string; progress: CollaborationProgress[]; result?: string; records?: CollaborationRecord[];
  departmentRequests?: Record<string, string>; completedDepartments?: string[];
};

export const departmentOptions = ["경영지원팀", "마케팅팀", "영업팀", "교육기획팀", "교육운영팀", "콘텐츠팀", "기술개발팀", "고객지원팀", "재무·회계팀", "법무·보안팀"];
export const inquirySources: InquirySource[] = ["사전 질문", "현장 질문", "현장 자료 요청", "만족도 설문", "감사 메일 회신", "개인 맞춤 메일 회신", "뉴스레터 회신", "개인 맞춤 콘텐츠 회신", "문의 답변 메일 회신", "전화", "메신저", "대면"];
export const contactChannels: ContactChannel[] = ["이메일", "전화", "메신저", "대면"];
export const requestTypes: RequestType[] = ["질문 답변", "자료 전달", "영업 관련 요청"];
export const inquiryStatusLabels: Record<InquiryStatus, string> = { answer_pending: "답변 대기", collaboration: "부서 협업 중", review: "검토 대기", completed: "답변 완료" };
export const collaborationStatusLabels: Record<CollaborationStatus, string> = { request_pending: "요청 대기", reply_pending: "회신 대기", confirmed: "확인 완료" };
export const inquiryStatusTones: Record<InquiryStatus, "warning" | "pending" | "muted" | "complete"> = { answer_pending: "warning", collaboration: "pending", review: "pending", completed: "complete" };
export const collaborationStatusTones: Record<CollaborationStatus, "warning" | "pending" | "complete"> = { request_pending: "warning", reply_pending: "pending", confirmed: "complete" };

// 실제 메일 수신·사내 알림·영구 저장이 연결되지 않은 화면 검증용 데이터입니다.
export const demoInquiries: Inquiry[] = [
  { id: "inq-001", customerId: "demo-customer-001", name: "예시 고객 01", company: "예시 기업 A", title: "교육담당자", email: "example01@demo.invalid", inquiryTitle: "AI 역량 진단 결과를 다시 확인하고 싶습니다", source: "사전 질문", currentChannel: "이메일", initialText: "행사 전에 AI 역량 진단 결과를 다시 받을 수 있는지 문의했습니다.", currentText: "진단 결과 재전달 가능 여부와 확인 방법을 안내해 주세요.", eventName: "CEO 인사이트 특강 · 서울", sentMailSubject: "행사 참석 감사 메일", firstContactAt: "2026-11-20", lastContactAt: "2026-11-26", types: ["질문 답변"], departments: [], status: "answer_pending", messages: [{ id: "msg-001", sentAt: "2026-11-20 10:20", direction: "inbound", channel: "이메일", sender: "예시 고객 01", body: "진단 결과를 다시 확인할 수 있을까요?" }], requests: [] },
  { id: "inq-002", customerId: "demo-customer-002", name: "예시 고객 02", company: "예시 기업 B", title: "HR 매니저", email: "example02@demo.invalid", inquiryTitle: "교육 실습 환경을 확인하고 싶습니다", source: "현장 질문", currentChannel: "전화", initialText: "현장에서 교육 실습 환경과 제공 범위를 질문했습니다.", currentText: "교육운영팀과 기술개발팀에 실습 환경 및 제공 범위를 확인해야 합니다.", eventName: "HR 담당자 AI 특강", firstContactAt: "2026-11-18", lastContactAt: "2026-11-25", types: ["질문 답변"], departments: ["교육운영팀", "기술개발팀"], status: "collaboration", messages: [{ id: "msg-002", sentAt: "2026-11-18 16:10", direction: "inbound", channel: "전화", sender: "예시 고객 02", body: "교육에서 사용하는 실습 환경과 제공 범위가 궁금합니다." }, { id: "msg-003", sentAt: "2026-11-25 09:00", direction: "internal", channel: "내부 메모", sender: "마케팅 담당자", body: "교육운영팀과 기술개발팀에 실습 환경 확인 요청을 등록했습니다." }], requests: [] },
  { id: "inq-003", customerId: "demo-customer-003", name: "예시 고객 03", company: "예시 기업 C", title: "팀 리더", email: "example03@demo.invalid", inquiryTitle: "행사 발표자료를 전달받고 싶습니다", source: "현장 자료 요청", currentChannel: "메신저", initialText: "행사에서 소개된 발표자료 전달을 요청했습니다.", currentText: "발표자료 링크를 확인한 뒤 전달할 예정입니다.", eventName: "AI 빌더톤 데모데이", firstContactAt: "2026-11-15", lastContactAt: "2026-11-24", types: ["자료 전달"], departments: ["콘텐츠팀"], status: "review", messages: [{ id: "msg-004", sentAt: "2026-11-15 18:30", direction: "inbound", channel: "메신저", sender: "예시 고객 03", body: "오늘 발표자료를 받아볼 수 있을까요?" }], requests: [] },
  { id: "inq-004", customerId: "demo-customer-004", name: "예시 고객 04", company: "예시 기업 D", title: "기획 담당자", email: "example04@demo.invalid", inquiryTitle: "뉴스레터의 관련 자료를 확인했습니다", source: "뉴스레터 회신", currentChannel: "이메일", initialText: "뉴스레터에서 소개된 자료에 대해 추가로 문의했습니다.", currentText: "관련 자료와 공개 범위를 확인해 답변해야 합니다.", contentTitle: "2026년 기업 교육 트렌드", firstContactAt: "2026-11-10", lastContactAt: "2026-11-23", types: ["자료 전달", "질문 답변"], departments: [], status: "answer_pending", messages: [{ id: "msg-005", sentAt: "2026-11-23 14:15", direction: "inbound", channel: "이메일", sender: "예시 고객 04", body: "본문에서 언급된 자료를 공유받을 수 있나요?" }], requests: [] },
  { id: "inq-005", customerId: "demo-customer-005", name: "예시 고객 05", company: "예시 기업 E", title: "대표", email: "example05@demo.invalid", inquiryTitle: "도입 검토 상담 결과를 확인했습니다", source: "개인 맞춤 메일 회신", currentChannel: "이메일", initialText: "개인 맞춤 메일에 회신하여 도입 관련 상담을 요청했습니다.", currentText: "상담 일정과 검토 결과를 정리해 회신할 예정입니다.", sentMailSubject: "AI 교육 도입 관련 안내", firstContactAt: "2026-11-12", lastContactAt: "2026-11-22", types: ["영업 관련 요청"], departments: ["영업팀"], status: "completed", messages: [{ id: "msg-006", sentAt: "2026-11-22 11:00", direction: "inbound", channel: "이메일", sender: "예시 고객 05", body: "도입 상담을 진행하고 싶습니다." }, { id: "msg-007", sentAt: "2026-11-22 16:30", direction: "outbound", channel: "이메일", sender: "이음러닝 담당자", body: "상담 일정 후보를 전달드렸습니다.", subject: "Re: AI 교육 도입 관련 안내" }], requests: [] },
];

export const demoCollaborations: CollaborationTask[] = [
  { id: "collab-001", inquiryId: "inq-002", customerId: "demo-customer-002", name: "예시 고객 02", company: "예시 기업 B", title: "교육 실습 환경을 확인하고 싶습니다", departments: ["교육운영팀", "기술개발팀"], registeredAt: "2026-11-25", dueDate: "2026-11-28", updatedAt: "2026-11-26", status: "reply_pending", requestBody: "교육 실습 환경과 고객에게 제공 가능한 범위를 확인해 주세요.", progress: [{ id: "progress-001", date: "2026-11-25", department: "교육운영팀", status: "요청 전달", note: "실습 운영 환경과 제공 범위를 확인 요청했습니다." }], records: [{ id: "record-001", department: "교육운영팀", direction: "outbound", kind: "협업 요청", occurredAt: "2026-11-25 09:00", channel: "내부 기록", body: "교육 실습 환경과 고객에게 제공 가능한 범위를 확인해 주세요." }, { id: "record-002", department: "교육운영팀", direction: "inbound", kind: "부서 회신", occurredAt: "2026-11-26 14:20", channel: "내부 기록", body: "기본 실습 환경은 제공 가능하며 세부 권한 범위는 추가 확인이 필요합니다." }] },
  { id: "collab-002", inquiryId: "inq-003", customerId: "demo-customer-003", name: "예시 고객 03", company: "예시 기업 C", title: "행사 발표자료를 전달받고 싶습니다", departments: ["콘텐츠팀"], registeredAt: "2026-11-24", dueDate: "2026-11-26", updatedAt: "2026-11-26", status: "request_pending", requestBody: "발표자료 최신 링크와 외부 공유 가능 여부를 확인해 주세요.", progress: [] },
];
