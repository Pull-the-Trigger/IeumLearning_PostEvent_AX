"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AlertTriangle, CalendarCheck, Check, ChevronDown, ChevronLeft, ChevronRight, ClipboardList, Clock3, History, Plus, Search, Send, Settings2, UserPlus, Users, X } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { StatusText } from "@/components/status-text";
import { CustomerProfile, RecipientFilter, ThankYouEvent, getBaseRecipients, getStatusLabel, getStatusTone, initialThankYouEvents, isValidEmail, isValidUrl, normalizeEmail, renderTemplate as renderTemplateText } from "@/lib/thank-you-mail-data";
import { getSurveyDefinitionForEvent } from "@/lib/survey-data";
import { SurveyManagementModal } from "@/components/survey-management-modal";

const DEFAULT_SENDER_NAME = "이음러닝 마케팅본부장 한서윤";
function getSenderName(event: ThankYouEvent) { return event.senderName?.trim() || DEFAULT_SENDER_NAME; }

function updateEvent(events: ThankYouEvent[], id: string, update: Partial<ThankYouEvent>) { return events.map((event) => event.id === id ? { ...event, ...update } : event); }
function isPastSchedule(date: string, time: string) { return new Date(`${date}T${time}:00+09:00`).getTime() < Date.now(); }
function getFinalRecipientProfiles(event: ThankYouEvent) { return event.recipients.filter((person) => (person.attended || event.addedRecipientIds.includes(person.id)) && isValidEmail(person.email) && !event.excludedRecipientIds.includes(person.id)); }
function getSeoulTimestamp() { return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul", dateStyle: "short", timeStyle: "medium" }).format(new Date()).replace(".", "-").replace(".", "-").replace(".", ""); }

export function ThankYouMailPage() {
  const [events, setEvents] = useState(initialThankYouEvents);
  const [selectedId, setSelectedId] = useState(initialThankYouEvents[0].id);
  const [editorOpen, setEditorOpen] = useState(false);
  const [surveyManagementOpen, setSurveyManagementOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<"unanswered" | "answered">("unanswered");
  const [confirmation, setConfirmation] = useState<"immediate" | "scheduled" | null>(null);
  const [sending, setSending] = useState(false);
  const browserOrigin = useSyncExternalStore(() => () => undefined, () => window.location.origin, () => "");
  const event = events.find((item) => item.id === selectedId) ?? events[0];
  const surveyDefinition = getSurveyDefinitionForEvent(event.id);
  const surveyUrl = surveyDefinition ? (browserOrigin ? `${browserOrigin}/survey/${surveyDefinition.token}` : `/survey/${surveyDefinition.token}`) : "";
  const mailEvent = { ...event, surveyUrl };
  const baseCount = getBaseRecipients(event).length;
  const finalCount = getFinalRecipientProfiles(event).length;
  const surveyPendingCount = event.includeSurvey && surveyUrl ? getBaseRecipients(event).filter((person) => !person.surveyResponded && !event.excludedRecipientIds.includes(person.id)).length : 0;
  const statusCounts = { draft: events.filter((item) => item.status === "draft").length, review: events.filter((item) => item.status === "review").length, scheduled: events.filter((item) => item.status === "scheduled").length, sent: events.filter((item) => item.status === "sent").length };
  const update = (patch: Partial<ThankYouEvent>) => setEvents((current) => updateEvent(current, event.id, Object.prototype.hasOwnProperty.call(patch, "lastApproval") ? patch : { ...patch, lastApproval: undefined }));

  function validateSendRequirements(requireSchedule: boolean) {
    if (event.senderName !== undefined && !event.senderName.trim()) return "발신자 정보를 입력해 주세요.";
    if (finalCount < 1) return "최종 발송 대상자가 없습니다.";
    if (!getFinalRecipientProfiles(event).every((person) => isValidEmail(person.email))) return "유효하지 않은 이메일 주소가 포함되어 있습니다.";
    if (!event.subject.trim() || !event.greeting.trim()) return "메일 제목과 본문을 작성해 주세요.";
    if (event.includeMaterials && !isValidUrl(event.materialsUrl)) return "발표자료 링크를 확인해 주세요.";
    if (event.includeSurvey && (!isValidUrl(surveyUrl) || !event.surveyParagraph.includes("이미 응답하셨다면 넘어가셔도 됩니다."))) return "만족도 조사 링크와 안내 문구를 확인해 주세요.";
    if (requireSchedule && (!event.scheduledDate || !event.scheduledTime)) return "발송 예정일과 시간을 설정해 주세요.";
    if (requireSchedule && isPastSchedule(event.scheduledDate, event.scheduledTime)) return "발송 예정 시각은 현재 시각 이후여야 합니다.";
    return null;
  }

  function requestConfirmation(type: "immediate" | "scheduled") {
    const error = validateSendRequirements(type === "scheduled");
    if (error) { window.alert(error); return; }
    setConfirmation(type);
  }

  function sendImmediately() {
    if (sending || event.status === "sent") return;
    setSending(true);
    update({ status: "sent", approved: true, lastApproval: undefined, history: [...event.history, { sentAt: getSeoulTimestamp(), count: finalCount, result: `성공 ${finalCount}건`, simulated: true }] });
    setConfirmation(null);
    setSending(false);
  }

  function approveScheduled() {
    if (sending) return;
    update({ status: "scheduled", approved: true, lastApproval: { approvedAt: getSeoulTimestamp(), scheduledAt: `${event.scheduledDate} ${event.scheduledTime}`, count: finalCount } });
    setConfirmation(null);
  }

  return <div className="mail-page">
    <div className="mail-breadcrumb"><Link href="/">홈</Link><span>/</span><Link href="/follow-up/thank-you">행사별 후속 관리</Link><span>/</span><strong>감사 메일</strong></div>
    <div className="mail-page-header"><div><p className="eyebrow">FOLLOW-UP MAIL</p><h1>감사 메일</h1><p>행사 참석자에게 감사 인사와 행사 관련 안내를 전달합니다.</p></div><span className="mock-badge">예시 데이터 사용 중</span></div>

    <section className="mail-section"><div className="mail-section-heading"><div><h2>업무 현황 요약</h2><p>행사별 감사 메일 상태를 기준으로 집계합니다.</p></div></div><div className="status-summary-grid"><SummaryCard label="작성 대기" count={statusCounts.draft} tone="warning" /><SummaryCard label="검토 대기" count={statusCounts.review} tone="pending" /><SummaryCard label="발송 예정" count={statusCounts.scheduled} tone="pending" /><SummaryCard label="발송 완료" count={statusCounts.sent} tone="complete" /></div></section>

    <section className="mail-card event-selector-card"><div className="card-heading"><div><span className="card-kicker">01</span><h2>행사 선택</h2></div><span className="data-source">통합 데이터 연동 대기 · E07 제외</span></div><div className="event-select-row"><div className="select-wrap"><select value={event.id} onChange={(e) => setSelectedId(e.target.value)} aria-label="행사 선택">{events.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={17} /></div><StatusText tone={getStatusTone(event.status)}>{getStatusLabel(event.status)}</StatusText></div><div className="event-facts"><Fact label="개최일" value={event.eventDate} /><Fact label="신청 인원" value={`${event.appliedCount}명`} /><Fact label="참석 인원" value={`${event.attendedCount}명`} /><Fact label="기본 발송 대상" value={`${baseCount}명`} /></div></section>

    <section className="mail-card"><CardTitle index="02" title="발송 대상 관리" action={<button className="secondary-button" type="button" onClick={() => setEditorOpen(true)}><Settings2 size={15} /> 대상 편집</button>} /><p className="card-description">실제 참석자 중 유효한 이메일이 있는 대상만 자동 구성합니다. 마케팅 수신 동의 여부는 감사 메일 대상 선정 조건으로 사용하지 않습니다.</p><div className="recipient-summary-grid"><Metric label="기본 대상" value={`${baseCount}명`} /><Metric label="추가" value={`${event.addedRecipientIds.length}명`} /><Metric label="제외" value={`${event.excludedRecipientIds.length}명`} /><Metric label="최종 발송" value={`${finalCount}명`} accent /></div><div className="info-banner"><Users size={16} /><span>통합 고객 프로필과 행사별 참석 정보는 현재 mock 어댑터로 표시됩니다. 원본 고객 파일은 브라우저로 복사하지 않습니다.</span></div></section>

    <section className="mail-card"><CardTitle index="03" title="만족도 조사 연동 현황" action={<button className="secondary-button" type="button" onClick={() => setSurveyManagementOpen(true)}><ClipboardList size={14} /> 만족도 조사 관리</button>} /><div className="survey-metrics"><Metric label="전체 설문 응답" value={`${event.surveyCount}건`} /><Metric label="이메일 식별 응답" value={`${event.surveyIdentifiedCount}건`} /><Metric label="익명 응답" value={`${event.surveyAnonymousCount}건`} /><Metric label="최종 대상 중 기응답" value={`${getBaseRecipients(event).filter((person) => person.surveyResponded && !event.excludedRecipientIds.includes(person.id)).length}명`} accent /></div><div className="info-banner muted-banner"><AlertTriangle size={16} /><span>응답 매칭은 현재 행사 ID와 정규화된 이메일 기준입니다. 이메일 없는 익명 응답은 임의로 매칭하지 않습니다.</span></div></section>

    <section className="mail-card"><CardTitle index="04" title="메일 포함 항목" /><div className="option-list"><label className="mail-option locked"><input type="checkbox" checked readOnly /><span><strong>감사 인사</strong><small>필수 항목</small></span><Check size={16} /></label><div className="mail-option mail-option-stack"><input type="checkbox" checked={event.includeMaterials} onChange={(e) => update({ includeMaterials: e.target.checked, approved: false, status: event.status === "sent" ? "sent" : "review" })} /><div className="mail-option-content"><strong>발표자료 링크</strong><div className="mail-link-field"><input aria-label="발표자료 링크" value={event.materialsUrl} onChange={(e) => update({ materialsUrl: e.target.value, approved: false, status: event.status === "sent" ? "sent" : "review" })} placeholder="https://" /><button className="secondary-button compact-button" type="button" disabled={!isValidUrl(event.materialsUrl)} onClick={() => window.open(event.materialsUrl, "_blank", "noopener,noreferrer")}>링크 확인</button></div><small>{event.materialsUrl ? (isValidUrl(event.materialsUrl) ? "HTTP 또는 HTTPS 링크" : "HTTP 또는 HTTPS 형식의 URL을 입력해 주세요.") : "등록된 링크가 없어 메일에서 제외됩니다."}</small></div></div><div className={`mail-option mail-option-stack ${!surveyDefinition ? "disabled" : ""}`}><input type="checkbox" checked={event.includeSurvey} disabled={!surveyDefinition} onChange={(e) => update({ includeSurvey: e.target.checked, approved: false, status: event.status === "sent" ? "sent" : "review" })} /><div className="mail-option-content"><strong>만족도 조사 요청</strong><div className="survey-link-row"><code>{surveyUrl || "행사에 연결된 설문이 없습니다."}</code><button className="secondary-button compact-button" type="button" disabled={!surveyUrl} onClick={() => window.open(`/survey/preview/${surveyDefinition?.token ?? ""}`, "_blank", "noopener,noreferrer")}>설문 미리보기</button><button className="secondary-button compact-button" type="button" disabled={!surveyUrl} onClick={() => navigator.clipboard.writeText(surveyUrl)}>링크 복사</button></div><small>행사별 참가자용 설문 링크가 자동으로 연결됩니다.</small></div></div></div></section>

    <section className="mail-card"><CardTitle index="05" title="감사 메일 문안" action={<span className="template-badge">공통 템플릿</span>} /><div className="mail-tabs"><button className={previewMode === "unanswered" ? "active" : ""} onClick={() => setPreviewMode("unanswered")} type="button">문안 수정</button><button className={previewMode === "answered" ? "active" : ""} onClick={() => setPreviewMode("answered")} type="button">메일 미리보기</button></div>{previewMode === "unanswered" ? <TemplateEditor event={event} onChange={update} /> : <MailPreview event={mailEvent} />}</section>

    <section className="mail-card"><CardTitle index="06" title="발송 일정 및 승인" /><div className="schedule-form-grid"><label>발송 예정일<DatePicker value={event.scheduledDate} onChange={(scheduledDate) => update({ scheduledDate, approved: false, status: event.status === "sent" ? "sent" : "review", lastApproval: undefined })} /></label><label>발송 예정 시간<TimePicker value={event.scheduledTime} onChange={(scheduledTime) => update({ scheduledTime, approved: false, status: event.status === "sent" ? "sent" : "review", lastApproval: undefined })} /></label><div className="timezone-note"><Clock3 size={15} /> Asia/Seoul 기준 · 행사 다음 날 오전 9시 기본값</div></div><div className="approval-facts"><Fact label="최종 발송 대상" value={`${finalCount}명`} /><Fact label="검토 대상 문안" value="공통 문안 1건" /><Fact label="발표자료 포함 대상" value={event.includeMaterials ? `${finalCount}명` : "0명"} /><Fact label="설문 요청 포함 대상" value={`${surveyPendingCount}명`} /></div><div className="approval-actions"><button className="primary-button" type="button" onClick={() => requestConfirmation("immediate")} disabled={event.status === "sent" || finalCount < 1}><Send size={15} /> 지금 발송</button><button className="primary-button" type="button" onClick={() => requestConfirmation("scheduled")} disabled={event.status === "sent" || finalCount < 1}><CalendarCheck size={15} /> 예약 발송 승인</button>{event.status === "scheduled" && <button className="text-button" type="button" onClick={() => update({ approved: false, status: "review", lastApproval: undefined })}>승인 취소</button>}</div>{event.status === "scheduled" && event.lastApproval && <p className="simulation-note">예약 발송 승인 완료 · {event.lastApproval.scheduledAt} · {event.lastApproval.count}명 대상</p>}{event.status === "sent" && event.history.length > 0 && <p className="simulation-note">모의 발송 완료 · {event.history[event.history.length - 1].sentAt} · {event.history[event.history.length - 1].count}명 발송</p>}</section>

    <section className="mail-card"><CardTitle index="07" title="발송 이력" /><div className="history-list">{event.history.length ? event.history.map((history) => <div className="history-row" key={history.sentAt}><span className="history-icon"><History size={16} /></span><div><strong>{history.sentAt}</strong><span>{history.count}명 · {history.result}</span></div><StatusText tone="complete">{history.simulated ? "모의 발송" : "발송"}</StatusText></div>) : <EmptyState message="아직 발송된 감사 메일이 없습니다." />}</div></section>

    {editorOpen && <RecipientEditorDialog event={event} onClose={() => setEditorOpen(false)} onApply={(excluded, recipients, added) => { update({ excludedRecipientIds: excluded, recipients, addedRecipientIds: added, approved: false, status: event.status === "sent" ? "sent" : "review", lastApproval: undefined }); setEditorOpen(false); }} />}
    {surveyManagementOpen && surveyDefinition && <SurveyManagementModal event={event} definition={surveyDefinition} publicUrl={surveyUrl} onClose={() => setSurveyManagementOpen(false)} />}
    {confirmation && <SendConfirmationDialog type={confirmation} event={event} count={finalCount} busy={sending} onClose={() => setConfirmation(null)} onConfirm={confirmation === "immediate" ? sendImmediately : approveScheduled} />}
  </div>;
}

function SummaryCard({ label, count, tone }: { label: string; count: number; tone: "warning" | "pending" | "complete" }) { return <div className={`summary-card summary-${tone}`}><span>{label}</span><strong>{count}<small>개 행사</small></strong></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="fact"><span>{label}</span><strong>{value}</strong></div>; }
function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) { return <div className={`metric ${accent ? "metric-accent" : ""}`}><span>{label}</span><strong>{value}</strong></div>; }
function CardTitle({ index, title, action }: { index: string; title: string; action?: React.ReactNode }) { return <div className="card-heading"><div><span className="card-kicker">{index}</span><h2>{title}</h2></div>{action}</div>; }

function parseLocalDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day) : new Date();
}

function formatDateValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function DatePicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => parseLocalDate(value));
  const selectedDate = parseLocalDate(value);
  const firstDay = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1).getDay();
  const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: firstDay + daysInMonth }, (_, index) => index < firstDay ? null : index - firstDay + 1);
  const selectDate = (day: number) => {
    onChange(formatDateValue(new Date(viewDate.getFullYear(), viewDate.getMonth(), day)));
    setOpen(false);
  };

  return <div className="date-picker"><button className="date-picker-trigger" type="button" onClick={() => { setViewDate(parseLocalDate(value)); setOpen((current) => !current); }} aria-haspopup="dialog" aria-expanded={open}><span>{value}</span><span aria-hidden="true">▣</span></button>{value && <button className="date-picker-clear" type="button" onClick={(event) => { event.stopPropagation(); onChange(""); setOpen(false); }} aria-label="날짜 초기화">×</button>}{open && <div className="date-picker-popover" role="dialog" aria-label="발송 예정일 선택"><div className="calendar-header"><button className="icon-button" type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))} aria-label="이전 달"><ChevronLeft size={15} /></button><strong>{viewDate.getFullYear()}년 {viewDate.getMonth() + 1}월</strong><button className="icon-button" type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))} aria-label="다음 달"><ChevronRight size={15} /></button></div><div className="calendar-weekdays">{["일", "월", "화", "수", "목", "금", "토"].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-grid">{cells.map((day, index) => day ? <button className={selectedDate.getFullYear() === viewDate.getFullYear() && selectedDate.getMonth() === viewDate.getMonth() && selectedDate.getDate() === day ? "selected" : ""} key={day} type="button" onClick={() => selectDate(day)}>{day}</button> : <span key={`empty-${index}`} />)}</div></div>}</div>;
}

function TimePicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [hourValue, minuteValue] = value.split(":").map(Number);
  const period = hourValue >= 12 ? "오후" : "오전";
  const hour = hourValue % 12 || 12;
  const update = (nextPeriod: string, nextHour: number, nextMinute: number) => {
    const hour24 = nextPeriod === "오후" ? (nextHour % 12) + 12 : nextHour % 12;
    onChange(`${String(hour24).padStart(2, "0")}:${String(nextMinute).padStart(2, "0")}`);
  };
  return <div className="time-picker"><select value={period} onChange={(event) => update(event.target.value, hour, minuteValue)} aria-label="오전 오후"><option>오전</option><option>오후</option></select><select value={hour} onChange={(event) => update(period, Number(event.target.value), minuteValue)} aria-label="시"><option value="12">12시</option>{Array.from({ length: 11 }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}시</option>)}</select><select value={minuteValue} onChange={(event) => update(period, hour, Number(event.target.value))} aria-label="분">{Array.from({ length: 12 }, (_, index) => <option key={index * 5} value={index * 5}>{String(index * 5).padStart(2, "0")}분</option>)}</select></div>;
}

function LegacyTemplateEditor({ event, onChange }: { event: ThankYouEvent; onChange: (patch: Partial<ThankYouEvent>) => void }) {
  return <div className="template-editor"><label>메일 제목<input value={event.subject} onChange={(e) => onChange({ subject: e.target.value, approved: false, status: event.status === "sent" ? "sent" : "review" })} /></label><label>공통 감사 인사<textarea rows={7} value={event.greeting} onChange={(e) => onChange({ greeting: e.target.value, approved: false, status: event.status === "sent" ? "sent" : "review" })} /></label><div className="template-columns"><label>발표자료 안내 문단<textarea rows={5} value={event.materialsParagraph} onChange={(e) => onChange({ materialsParagraph: e.target.value, approved: false })} /></label><label>만족도 조사 안내 문단<textarea rows={5} value={event.surveyParagraph} onChange={(e) => onChange({ surveyParagraph: e.target.value, approved: false })} /></label></div><p className="template-help">치환 변수: <code>{"{{이름}}"}</code> <code>{"{{호칭}}"}</code> <code>{"{{행사명}}"}</code> <code>{"{{발표자료링크}}"}</code> <code>{"{{만족도조사링크}}"}</code></p><div className="sender-signature"><span>발신자</span><strong>이음러닝 마케팅본부장 한서윤</strong><small>실제 발신 이메일 주소는 확인된 설정값이 없어 표시하지 않습니다.</small></div></div>;
}

function TemplateEditor({ event, onChange }: { event: ThankYouEvent; onChange: (patch: Partial<ThankYouEvent>) => void }) {
  const updateSender = (value: string) => onChange({ senderName: value, approved: false, status: event.status === "sent" ? "sent" : "review" });
  return <div className="template-editor"><label>메일 제목<input value={event.subject} onChange={(e) => onChange({ subject: e.target.value, approved: false, status: event.status === "sent" ? "sent" : "review" })} /></label><label>공통 감사 인사<textarea rows={7} value={event.greeting} onChange={(e) => onChange({ greeting: e.target.value, approved: false, status: event.status === "sent" ? "sent" : "review" })} /></label><div className="template-columns"><label>발표자료 안내 문단<textarea rows={5} value={event.materialsParagraph} onChange={(e) => onChange({ materialsParagraph: e.target.value, approved: false })} /></label><label>만족도 조사 안내 문단<textarea rows={5} value={event.surveyParagraph} onChange={(e) => onChange({ surveyParagraph: e.target.value, approved: false })} /></label></div><p className="template-help">치환 변수: <code>{"{{이름}}"}</code> <code>{"{{호칭}}"}</code> <code>{"{{행사명}}"}</code> <code>{"{{발표자료링크}}"}</code> <code>{"{{만족도조사링크}}"}</code></p><div className="sender-signature"><span>발신자</span><input aria-label="발신자" value={event.senderName ?? DEFAULT_SENDER_NAME} onChange={(e) => updateSender(e.target.value)} /></div></div>;
}

function renderTemplate(event: ThankYouEvent, person: CustomerProfile, includeSurvey: boolean) {
  const body = renderTemplateText(event, person, includeSurvey);
  const defaultSignature = `${DEFAULT_SENDER_NAME} 드림`;
  return renderPreviewBody(body.endsWith(defaultSignature) ? `${body.slice(0, -defaultSignature.length)}${getSenderName(event)} 드림` : body);
}
function renderPreviewBody(body: string) {
  return body.split(/(https?:\/\/[^\s<]+)/gi).map((part, index) => {
    if (!/^https?:\/\//i.test(part)) return <span key={index}>{part}</span>;
    try {
      const url = new URL(part);
      if (url.protocol !== "http:" && url.protocol !== "https:") return <span key={index}>{part}</span>;
      return <a key={index} href={part} target="_blank" rel="noopener noreferrer">{part}</a>;
    } catch {
      return <span key={index}>{part}</span>;
    }
  });
}

function LegacyMailPreview({ event }: { event: ThankYouEvent }) {
  const [mode, setMode] = useState<"unanswered" | "answered">("unanswered");
  const candidates = getBaseRecipients(event).filter((item) => item.surveyResponded === (mode === "answered"));
  const person = candidates[0] ?? getBaseRecipients(event)[0];
  const includeSurvey = mode === "unanswered" && !person.surveyResponded;
  return <div className="mail-preview"><div className="preview-toolbar"><div className="preview-switch"><button className={mode === "unanswered" ? "active" : ""} type="button" onClick={() => setMode("unanswered")}>설문 응답 미확인</button><button className={mode === "answered" ? "active" : ""} type="button" onClick={() => setMode("answered")}>설문 응답 확인</button></div><StatusText tone="muted">{person.name} · {candidates.length ? "예시 미리보기" : "해당 유형 없음"}</StatusText></div><div className="preview-meta"><span>발신자</span><strong>이음러닝 마케팅본부장 한서윤</strong><span>수신자</span><strong>{person.email}</strong><span>제목</span><strong>{event.subject.replaceAll("{{행사명}}", event.name)}</strong></div><pre>{renderTemplate(event, person, includeSurvey)}</pre>{!includeSurvey && event.includeSurvey && <p className="preview-note">이 수신자는 해당 행사 설문 응답이 확인되어 설문 요청 문단과 링크가 제외되었습니다.</p>}</div>;
}

void LegacyTemplateEditor;
void LegacyMailPreview;

function MailPreview({ event }: { event: ThankYouEvent }) {
  const [mode, setMode] = useState<"unanswered" | "answered">("unanswered");
  const candidates = getBaseRecipients(event).filter((item) => item.surveyResponded === (mode === "answered"));
  const person = candidates[0] ?? getBaseRecipients(event)[0];
  if (!person) return <EmptyState message="유효한 발송 대상자가 없어 메일 미리보기를 표시할 수 없습니다." />;
  const includeSurvey = mode === "unanswered" && !person.surveyResponded;
  return <div className="mail-preview"><div className="preview-toolbar"><div className="preview-switch"><button className={mode === "unanswered" ? "active" : ""} type="button" onClick={() => setMode("unanswered")}>설문 응답 미확인</button><button className={mode === "answered" ? "active" : ""} type="button" onClick={() => setMode("answered")}>설문 응답 확인</button></div><StatusText tone="muted">{person.name} · {candidates.length ? "예시 미리보기" : "해당 유형 없음"}</StatusText></div><div className="preview-meta"><span>발신자</span><strong>{getSenderName(event)}</strong><span>수신자</span><strong>{person.email}</strong><span>제목</span><strong>{event.subject.replaceAll("{{행사명}}", event.name)}</strong></div><pre>{renderTemplate(event, person, includeSurvey)}</pre>{!includeSurvey && event.includeSurvey && <p className="preview-note">이 수신자는 해당 행사 설문 응답이 확인되어 설문 요청 문단과 링크가 제외되었습니다.</p>}</div>;
}

function SendConfirmationDialog({ type, event, count, busy, onClose, onConfirm }: { type: "immediate" | "scheduled"; event: ThankYouEvent; count: number; busy: boolean; onClose: () => void; onConfirm: () => void }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);
  if (typeof document === "undefined") return null;
  const immediate = type === "immediate";
  return createPortal(<div className="modal-backdrop confirmation-backdrop" role="presentation"><div className="send-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="send-confirm-title"><div className="send-confirm-icon"><Send size={20} /></div><h2 id="send-confirm-title">{immediate ? "감사 메일 즉시 발송" : "감사 메일 예약 발송 승인"}</h2>{immediate ? <><p>최종 발송 대상 <strong>{count}명</strong>에게 감사 메일을 지금 발송하시겠습니까?</p><p className="send-confirm-warning">발송이 완료되면 취소할 수 없습니다.</p>{event.status === "scheduled" && <p className="send-confirm-warning">현재 예약 발송은 즉시 발송으로 대체됩니다.</p>}</> : <><p>다음 일정에 감사 메일을 발송하도록 승인하시겠습니까?</p><dl className="send-confirm-facts"><dt>발송 대상</dt><dd>{count}명</dd><dt>발송 예정일</dt><dd>{event.scheduledDate}</dd><dt>발송 예정 시간</dt><dd>{event.scheduledTime} (Asia/Seoul)</dd></dl><p className="send-confirm-note">예약 발송은 발송 예정 시각 전까지 변경하거나 취소할 수 있습니다.</p></>}<div className="send-confirm-actions"><button className="secondary-button" type="button" onClick={onClose} disabled={busy}>취소</button><button className="primary-button" type="button" onClick={onConfirm} disabled={busy}>{busy ? "처리 중..." : immediate ? <><Send size={15} /> 지금 발송</> : <><CalendarCheck size={15} /> 예약 발송 승인</>}</button></div></div></div>, document.body);
}

function RecipientEditorDialog({ event, onClose, onApply }: { event: ThankYouEvent; onClose: () => void; onApply: (excluded: string[], recipients: CustomerProfile[], added: string[]) => void }) {
  const [excluded, setExcluded] = useState(() => new Set(event.excludedRecipientIds));
  const [recipients, setRecipients] = useState(event.recipients);
  const [added, setAdded] = useState(event.addedRecipientIds);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<RecipientFilter>("all");
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<CustomerProfile | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [newPerson, setNewPerson] = useState({ name: "", company: "", title: "", email: "" });
  const base = getBaseRecipients({ ...event, recipients });
  const filtered = recipients.filter((person) => {
    const matchesQuery = [person.name, person.company, person.title, person.email].some((value) => value.toLowerCase().includes(query.toLowerCase()));
    const included = !excluded.has(person.id);
    return matchesQuery && (filter === "all" || (filter === "included" && included) || (filter === "excluded" && !included));
  });
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const finalCount = base.filter((person) => !excluded.has(person.id)).length + added.length;
  const toggle = (id: string) => setExcluded((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const allFilteredIncluded = filtered.length > 0 && filtered.every((person) => !excluded.has(person.id));
  const toggleFiltered = () => setExcluded((current) => { const next = new Set(current); filtered.forEach((person) => allFilteredIncluded ? next.add(person.id) : next.delete(person.id)); return next; });
  const allVisibleIncluded = allFilteredIncluded;
  const toggleVisible = toggleFiltered;
  const addPerson = () => {
    if (!newPerson.name.trim() || !isValidEmail(newPerson.email) || recipients.some((person) => normalizeEmail(person.email) === normalizeEmail(newPerson.email))) return;
    const person: CustomerProfile = { id: `${event.id}-added-${Date.now()}`, name: newPerson.name.trim(), company: newPerson.company.trim(), title: newPerson.title.trim(), email: normalizeEmail(newPerson.email), attended: true, consent: "UNKNOWN", attendanceCount: 1, surveyResponded: false };
    setRecipients((current) => [...current, person]); setAdded((current) => [...current, person.id]); setNewPerson({ name: "", company: "", title: "", email: "" }); setAddOpen(false);
  };
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  if (typeof document === "undefined") return null;

  return createPortal(<div className="modal-backdrop" role="presentation"><div className="recipient-modal" role="dialog" aria-modal="true" aria-label="발송 대상 편집"><div className="modal-header"><div><p className="eyebrow">RECIPIENTS</p><h2>발송 대상 편집</h2><p>{event.name} · 참석자 {event.attendedCount}명</p></div><button className="icon-button" onClick={onClose} type="button" aria-label="닫기"><X size={20} /></button></div><div className="modal-summary"><Metric label="기본 대상" value={`${base.length}명`} /><Metric label="추가 대상" value={`${added.length}명`} /><Metric label="제외 대상" value={`${excluded.size}명`} /><Metric label="최종 발송" value={`${finalCount}명`} accent /></div><div className="modal-toolbar"><div className="search-input"><Search size={16} /><input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="이름, 회사, 직함, 이메일 검색" /></div><div className="filter-tabs">{(["all", "included", "excluded"] as RecipientFilter[]).map((item) => <button className={filter === item ? "active" : ""} key={item} onClick={() => { setFilter(item); setPage(1); }} type="button">{{ all: "전체 대상", included: "발송 대상", excluded: "제외 대상" }[item]}</button>)}</div><button className="secondary-button" type="button" onClick={() => setAddOpen(true)}><UserPlus size={15} /> 참석자 추가</button></div>{addOpen && <div className="add-person-panel"><div className="add-person-heading"><strong>누락된 참석자 직접 등록</strong><button className="icon-button" type="button" onClick={() => setAddOpen(false)} aria-label="등록 닫기"><X size={16} /></button></div><div className="add-fields">{(["name", "company", "title", "email"] as const).map((field) => <input key={field} value={newPerson[field]} onChange={(e) => setNewPerson({ ...newPerson, [field]: e.target.value })} placeholder={{ name: "이름 *", company: "회사명", title: "직함", email: "이메일 *" }[field]} />)}<button className="primary-button" type="button" onClick={addPerson}><Plus size={14} /> 등록</button></div><small>이름과 유효한 이메일이 필요하며, 기존 이메일과 중복 등록할 수 없습니다.</small></div>}<div className="recipient-table-wrap"><table className="recipient-table"><thead><tr><th><input type="checkbox" checked={allVisibleIncluded} onChange={toggleVisible} aria-label="현재 결과 전체 선택" /></th><th>이름</th><th>회사</th><th>직함</th><th>이메일</th><th>설문 응답</th></tr></thead><tbody>{visible.map((person) => { const included = !excluded.has(person.id); return <tr key={person.id} className={!included ? "excluded-row" : ""}><td><input type="checkbox" checked={included} onChange={() => toggle(person.id)} aria-label={`${person.name} 발송 대상`} /></td><td><button className="person-link" type="button" onClick={() => setDetail(person)}>{person.name}</button></td><td>{person.company || "미등록"}</td><td>{person.title || "미등록"}</td><td className="email-cell">{person.email}</td><td><span className={`survey-dot ${person.surveyResponded ? "answered" : "unanswered"}`}>{person.surveyResponded ? "확인" : "미확인"}</span></td></tr>; })}</tbody></table>{visible.length === 0 && <EmptyState message="조건에 맞는 대상이 없습니다." />}</div><div className="pagination"><span>전체 {filtered.length}명 중 {filtered.length ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, filtered.length)}` : "0"}명</span><div><select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} aria-label="페이지당 표시 수"><option value="10">10명</option><option value="20">20명</option><option value="50">50명</option></select><button className="page-button" disabled={page <= 1} onClick={() => setPage(page - 1)} type="button"><ChevronLeft size={15} /></button><span>{page} / {pageCount}</span><button className="page-button" disabled={page >= pageCount} onClick={() => setPage(page + 1)} type="button"><ChevronRight size={15} /></button></div></div>{detail && <CustomerProfileDetail person={detail} onClose={() => setDetail(null)} />}<div className="modal-footer"><strong>최종 발송 대상 {finalCount}명</strong><div><button className="text-button" type="button" onClick={() => setExcluded(new Set())}>전체 복원</button><button className="secondary-button" type="button" onClick={onClose}>취소</button><button className="primary-button" type="button" onClick={() => onApply([...excluded], recipients, added)}>적용</button></div></div></div></div>, document.body);
}

function CustomerProfileDetail({ person, onClose }: { person: CustomerProfile; onClose: () => void }) { return <aside className="profile-panel"><div className="profile-panel-header"><strong>통합 고객 프로필</strong><button className="icon-button" type="button" onClick={onClose} aria-label="상세 닫기"><X size={16} /></button></div><div className="profile-avatar">{person.name.slice(-2)}</div><h3>{person.name}</h3><p>{person.company} · {person.title}</p><dl><dt>이메일</dt><dd>{person.email}</dd><dt>현재 행사 참석</dt><dd>{person.attended ? "참석" : "미참석"}</dd><dt>마케팅 수신 동의</dt><dd>{person.consent === "UNKNOWN" ? "확인 불가" : person.consent === "Y" ? "동의" : "미동의"}</dd><dt>누적 행사 참석</dt><dd>{person.attendanceCount}회</dd><dt>사전 질문</dt><dd>{person.preQuestion ?? "미등록"}</dd><dt>후속 연락</dt><dd>{person.interactionMemo ?? "미등록"}</dd></dl></aside>; }
