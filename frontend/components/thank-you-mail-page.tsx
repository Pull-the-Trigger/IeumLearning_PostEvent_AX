"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AlertTriangle, CalendarCheck, ChevronDown, ChevronLeft, ChevronRight, ClipboardList, Clock3, ExternalLink, History, Lock, Search, Send, Settings2, UserPlus, Users, X } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { StatusText } from "@/components/status-text";
import { getStatusLabel, getStatusTone, type RecipientFilter } from "@/lib/thank-you-mail-data";
import { surveyDefinitions } from "@/lib/survey-data";
import { getSurveyRows, type SurveyRow } from "@/lib/data-management-data";
import { approveThanks, cancelThanks, getHealth, getThanksDetail, getThanksList, nextDay, type ThanksApprovalStatus, type ThanksDetail, type ThanksRecipient, type ThanksSummary } from "@/lib/thanks-api";
import { SurveyManagementModal } from "@/components/survey-management-modal";

const LOAD_ERROR_MESSAGE = "데이터를 불러오지 못했습니다. 백엔드 서버가 켜져 있는지 확인해 주세요.";
const DEFAULT_SCHEDULE_TIME = "09:00";

type Load<T> = { status: "loading" } | { status: "error" } | { status: "ready"; data: T };
type Schedule = { date: string; time: string };
type Notice = { eventId: string; tone: "complete" | "warning" | "danger"; lines: string[] };

function errorMessage(error: unknown) { return error instanceof Error ? error.message : String(error); }
function serverExcluded(detail: ThanksDetail) { return new Set(detail.recipients.filter((person) => person.approvalStatus === "excluded").map((person) => person.email)); }
function sameSet(a: Set<string>, b: Set<string>) { return a.size === b.size && [...a].every((value) => b.has(value)); }
function shortTime(value?: string) { return value ? value.slice(0, 16) : ""; }
function bodyLinks(recipients: ThanksRecipient[]) { return [...new Set(recipients.flatMap((person) => person.body.match(/https?:\/\/[^\s<]+/gi) ?? []))]; }
function linkLabel(url: string) { return /\/slides?\//i.test(url) ? "발표 자료" : /\/survey\//i.test(url) ? "만족도 설문" : "링크"; }
function surveyDefinitionFor(eventId: string) { return surveyDefinitions.find((item) => item.token.startsWith(`${eventId.toLowerCase()}-`)); }

export function ThankYouMailPage() {
  const [list, setList] = useState<Load<ThanksSummary[]>>({ status: "loading" });
  const [details, setDetails] = useState<Record<string, Load<ThanksDetail>>>({});
  const [selectedId, setSelectedId] = useState("");
  const [today, setToday] = useState<string | null>(null);
  const [surveyRows, setSurveyRows] = useState<SurveyRow[] | null>(null);
  const [excludedByEvent, setExcludedByEvent] = useState<Record<string, Set<string>>>({});
  const [scheduleByEvent, setScheduleByEvent] = useState<Record<string, Schedule>>({});
  const [editorOpen, setEditorOpen] = useState(false);
  const [surveyManagementOpen, setSurveyManagementOpen] = useState(false);
  const [previewTab, setPreviewTab] = useState<"edit" | "preview">("preview");
  const [confirmation, setConfirmation] = useState<"immediate" | "scheduled" | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const requested = useRef(new Set<string>());
  const browserOrigin = useSyncExternalStore(() => () => undefined, () => window.location.origin, () => "");

  useEffect(() => {
    getThanksList().then((rows) => {
      setList({ status: "ready", data: rows });
      setSelectedId((current) => current || rows[0]?.eventId || "");
    }).catch(() => setList({ status: "error" }));
    getHealth().then((health) => setToday(health.today)).catch(() => setToday(""));
    getSurveyRows().then(setSurveyRows).catch(() => setSurveyRows(null));
  }, []);

  function loadDetail(eventId: string, syncExcluded: boolean) {
    return getThanksDetail(eventId).then((detail) => {
      setDetails((current) => ({ ...current, [eventId]: { status: "ready", data: detail } }));
      setExcludedByEvent((current) => (syncExcluded || !current[eventId] ? { ...current, [eventId]: serverExcluded(detail) } : current));
      setList((current) => current.status === "ready" ? { status: "ready", data: current.data.map((row) => row.eventId === eventId ? summaryOf(detail) : row) } : current);
    }).catch(() => {
      requested.current.delete(eventId);
      setDetails((current) => ({ ...current, [eventId]: { status: "error" } }));
    });
  }

  useEffect(() => {
    if (!selectedId || requested.current.has(selectedId)) return;
    requested.current.add(selectedId);
    void loadDetail(selectedId, false);
  }, [selectedId]);

  if (list.status !== "ready") {
    return <div className="mail-page">
      <PageHeader />
      <EmptyState message={list.status === "loading" ? "데이터를 불러오는 중입니다." : LOAD_ERROR_MESSAGE} />
    </div>;
  }

  const events = list.data;
  const event = events.find((item) => item.eventId === selectedId) ?? events[0];
  if (!event) return <div className="mail-page"><PageHeader /><EmptyState message="감사 메일을 보낼 행사가 없습니다." /></div>;

  const detailLoad = details[event.eventId] ?? { status: "loading" as const };
  const detail = detailLoad.status === "ready" ? detailLoad.data : null;
  const recipients = detail?.recipients ?? [];
  const excluded = excludedByEvent[event.eventId] ?? new Set<string>();
  const included = recipients.filter((person) => !excluded.has(person.email));
  const finalCount = included.length;
  const exclusionsDirty = detail ? !sameSet(excluded, serverExcluded(detail)) : false;
  const approvalInvalid = recipients.some((person) => person.approvalInvalid);
  const isSent = event.status === "sent";
  const defaultSchedule: Schedule = event.scheduledAt ? { date: event.scheduledAt.slice(0, 10), time: event.scheduledAt.slice(11, 16) } : { date: today ? nextDay(today) : "", time: DEFAULT_SCHEDULE_TIME };
  const schedule = scheduleByEvent[event.eventId] ?? defaultSchedule;
  const surveyIncludedCount = included.filter((person) => person.surveyIncluded).length;
  const eventSurveys = surveyRows?.filter((row) => row.eventId === event.eventId) ?? null;
  const surveyDefinition = surveyDefinitionFor(event.eventId);
  const surveyUrl = surveyDefinition ? `${browserOrigin}/survey/${surveyDefinition.token}` : "";
  const links = bodyLinks(recipients);
  const statusCounts = { draft: 0, review: 0, scheduled: 0, sent: 0 };
  events.forEach((item) => { statusCounts[item.status] += 1; });
  const eventNotice = notice?.eventId === event.eventId ? notice : null;
  const canApprove = !!detail && !isSent && !busy && finalCount > 0;

  function selectEvent(eventId: string) { setSelectedId(eventId); setNotice(null); }
  function setSchedule(patch: Partial<Schedule>) { setScheduleByEvent((current) => ({ ...current, [event.eventId]: { ...schedule, ...patch } })); }

  function requestConfirmation(type: "immediate" | "scheduled") {
    if (type === "scheduled" && (!schedule.date || !schedule.time)) { setNotice({ eventId: event.eventId, tone: "danger", lines: ["발송 예정일과 시간을 설정해 주세요."] }); return; }
    setConfirmation(type);
  }

  async function approve(mode: "now" | "scheduled") {
    if (busy) return;
    const eventId = event.eventId;
    setBusy(true);
    try {
      const result = await approveThanks(eventId, { mode, scheduledAt: mode === "scheduled" ? `${schedule.date} ${schedule.time}` : undefined, excludedEmails: [...excluded] });
      const done = mode === "now" ? `발송 처리했어요 · ${shortTime(result.sentAt)} · ${result.draftCount - result.excludedCount}명 (실제 메일은 보내지 않고 상태만 기록)` : `예약 발송을 승인했어요 · ${shortTime(result.scheduledAt)} · ${result.draftCount - result.excludedCount}명`;
      setNotice({ eventId, tone: result.warnings.length ? "warning" : "complete", lines: [done, ...result.warnings] });
      await loadDetail(eventId, true);
    } catch (error) {
      setNotice({ eventId, tone: "danger", lines: [errorMessage(error)] });
      await loadDetail(eventId, false);
    } finally {
      setBusy(false);
      setConfirmation(null);
    }
  }

  async function cancel() {
    if (busy) return;
    const eventId = event.eventId;
    setBusy(true);
    try {
      await cancelThanks(eventId);
      setNotice({ eventId, tone: "complete", lines: ["예약 발송 승인을 취소했어요."] });
    } catch (error) {
      setNotice({ eventId, tone: "danger", lines: [errorMessage(error)] });
    } finally {
      await loadDetail(eventId, false);
      setBusy(false);
    }
  }

  return <div className="mail-page">
    <PageHeader />

    <section className="mail-section"><div className="mail-section-heading"><div><h2>업무 현황 요약</h2><p>행사별 감사 메일 상태를 기준으로 집계합니다.</p></div></div><div className="status-summary-grid"><SummaryCard label="작성 대기" count={statusCounts.draft} tone="warning" /><SummaryCard label="검토 대기" count={statusCounts.review} tone="pending" /><SummaryCard label="발송 예정" count={statusCounts.scheduled} tone="pending" /><SummaryCard label="발송 완료" count={statusCounts.sent} tone="complete" /></div></section>

    <section className="mail-card event-selector-card"><div className="card-heading"><div><span className="card-kicker">01</span><h2>행사 선택</h2></div><span className="data-source">감사 메일 초안 DB 연동</span></div><div className="event-select-row"><div className="select-wrap"><select value={event.eventId} onChange={(e) => selectEvent(e.target.value)} aria-label="행사 선택">{events.map((item) => <option key={item.eventId} value={item.eventId}>{item.eventId} · {item.eventName}</option>)}</select><ChevronDown size={17} /></div><StatusText tone={getStatusTone(event.status)}>{getStatusLabel(event.status)}</StatusText></div><div className="event-facts"><Fact label="개최일" value={event.eventDate} /><Fact label="메일 초안" value={`${event.draftCount}건`} /><Fact label="발송 기한" value={event.sendBy ? `${event.sendBy}${event.sendByPassed ? " · 기한 지남" : ""}` : "—"} /><Fact label="제외(승인 기준)" value={`${event.excludedCount}명`} /></div></section>

    {detailLoad.status !== "ready" ? <section className="mail-card"><EmptyState message={detailLoad.status === "loading" ? "데이터를 불러오는 중입니다." : LOAD_ERROR_MESSAGE} /></section> : <>
      {approvalInvalid && <div className="info-banner"><AlertTriangle size={16} /><span>내용이 바뀌어 다시 승인이 필요해요. (승인 후 제목·본문이 바뀐 받는 사람 {recipients.filter((person) => person.approvalInvalid).length}명)</span></div>}

      <section className="mail-card"><CardTitle index="02" title="발송 대상 관리" action={<button className="secondary-button" type="button" onClick={() => setEditorOpen(true)} disabled={recipients.length === 0}><Settings2 size={15} /> 대상 편집</button>} /><p className="card-description">감사 메일 초안이 만들어진 참석자가 기본 대상입니다. 제외할 사람은 대상 편집에서 체크를 풀고, 승인할 때 함께 반영됩니다.</p><div className="recipient-summary-grid"><Metric label="기본 대상" value={`${recipients.length}명`} /><Metric label="제외" value={`${excluded.size}명`} /><Metric label="설문 요청 포함" value={`${surveyIncludedCount}명`} /><Metric label="최종 발송" value={`${finalCount}명`} accent /></div>{exclusionsDirty && !isSent && <div className="info-banner"><Users size={16} /><span>{event.status === "scheduled" ? "발송 대상이 바뀌었어요. 다시 승인해야 반영돼요." : "발송 대상 변경은 승인할 때 반영돼요."}</span></div>}</section>

      <section className="mail-card"><CardTitle index="03" title="만족도 조사 연동 현황" action={<button className="secondary-button" type="button" onClick={() => setSurveyManagementOpen(true)}><ClipboardList size={14} /> 만족도 조사 관리</button>} /><div className="survey-metrics"><Metric label="전체 설문 응답" value={eventSurveys ? `${eventSurveys.length}건` : "미확인"} /><Metric label="이메일 식별 응답" value={eventSurveys ? `${eventSurveys.filter((row) => row.identified).length}건` : "미확인"} /><Metric label="설문 요청 포함" value={`${surveyIncludedCount}명`} /><Metric label="설문 요청 미포함" value={`${finalCount - surveyIncludedCount}명`} accent /></div><div className="info-banner muted-banner"><AlertTriangle size={16} /><span>행사 당일 이메일을 적어 설문에 응답한 참석자는 설문 요청 문단이 빠진 초안으로 만들어집니다.</span></div></section>

      <section className="mail-card"><CardTitle index="04" title="자료·설문 링크" action={<span className="template-badge"><Lock size={11} /> 보기 전용</span>} /><div className="option-list">{links.length ? links.map((url) => <div className="mail-option mail-option-stack" key={url}><div className="mail-option-content"><strong>{linkLabel(url)}</strong><div className="survey-link-row"><code>{url}</code><button className="secondary-button compact-button" type="button" onClick={() => window.open(url, "_blank", "noopener,noreferrer")}><ExternalLink size={13} /> 링크 확인</button></div></div></div>) : <EmptyState message="메일 본문에 들어간 링크가 없습니다." />}</div><p className="template-help">링크는 감사 메일 초안 본문에 들어간 값입니다. 화면에서는 수정할 수 없습니다.</p></section>

      <section className="mail-card"><CardTitle index="05" title="감사 메일 문안" action={<span className="template-badge">초안 그대로 표시</span>} /><div className="mail-tabs"><button className={previewTab === "edit" ? "active" : ""} type="button" disabled title="문안 수정 기능 준비 중">문안 수정</button><button className={previewTab === "preview" ? "active" : ""} onClick={() => setPreviewTab("preview")} type="button">메일 미리보기</button></div><p className="template-help">문안 수정 기능 준비 중입니다.</p><MailPreview key={event.eventId} recipients={recipients} excluded={excluded} /></section>

      <section className="mail-card"><CardTitle index="06" title="발송 일정 및 승인" /><div className="schedule-form-grid"><label>발송 예정일<DatePicker value={schedule.date} onChange={(date) => setSchedule({ date })} /></label><label>발송 예정 시간<TimePicker value={schedule.time} onChange={(time) => setSchedule({ time })} /></label><div className="timezone-note"><Clock3 size={15} /> Asia/Seoul 기준 · 기본값 기준일({today || "미확인"}) 다음 날 오전 9시</div></div><div className="approval-facts"><Fact label="최종 발송 대상" value={`${finalCount}명`} /><Fact label="검토 대상 문안" value={`받는 사람별 초안 ${recipients.length}건`} /><Fact label="설문 요청 포함 대상" value={`${surveyIncludedCount}명`} /><Fact label="발송 기한" value={event.sendBy ?? "—"} /></div><div className="approval-actions"><button className="primary-button" type="button" onClick={() => requestConfirmation("immediate")} disabled={!canApprove}><Send size={15} /> 지금 발송</button><button className="primary-button" type="button" onClick={() => requestConfirmation("scheduled")} disabled={!canApprove}><CalendarCheck size={15} /> 예약 발송 승인</button><button className="text-button" type="button" onClick={cancel} disabled={busy || event.status !== "scheduled"}>승인 취소</button></div>{today === "" && <p className="simulation-note">기준일(/health)을 불러오지 못해 발송 예정일 기본값을 정하지 못했습니다. 날짜를 직접 골라 주세요.</p>}{event.status === "scheduled" && event.scheduledAt && <p className="simulation-note">예약 발송 승인 완료 · {shortTime(event.scheduledAt)} · {event.draftCount - event.excludedCount}명 대상</p>}{isSent && <p className="simulation-note">발송 완료 · {shortTime(event.sentAt)} · 발송된 메일은 다시 승인하거나 취소할 수 없습니다.</p>}{eventNotice && <div className={`info-banner ${eventNotice.tone === "warning" ? "" : "muted-banner"}`}><StatusText tone={eventNotice.tone}>{eventNotice.tone === "danger" ? "오류" : eventNotice.tone === "warning" ? "확인 필요" : "완료"}</StatusText><span>{eventNotice.lines.map((line, index) => <span key={line}>{index > 0 && <br />}{line}</span>)}</span></div>}</section>

      <section className="mail-card"><CardTitle index="07" title="발송 이력" /><div className="history-list">{isSent ? <div className="history-row"><span className="history-icon"><History size={16} /></span><div><strong>{shortTime(event.sentAt)}</strong><span>{event.draftCount - event.excludedCount}명 · 제외 {event.excludedCount}명</span></div><StatusText tone="complete">상태 기록</StatusText></div> : <EmptyState message="아직 발송된 감사 메일이 없습니다." />}</div></section>
    </>}

    {editorOpen && detail && <RecipientEditorDialog eventName={event.eventName} recipients={recipients} initialExcluded={excluded} readOnly={isSent} onClose={() => setEditorOpen(false)} onApply={(next) => { setExcludedByEvent((current) => ({ ...current, [event.eventId]: next })); setEditorOpen(false); }} />}
    {surveyManagementOpen && <SurveyManagementModal eventId={event.eventId} eventName={event.eventName} definition={surveyDefinition} publicUrl={surveyUrl} onClose={() => setSurveyManagementOpen(false)} />}
    {confirmation && <SendConfirmationDialog type={confirmation} status={event.status} count={finalCount} schedule={schedule} busy={busy} onClose={() => setConfirmation(null)} onConfirm={() => approve(confirmation === "immediate" ? "now" : "scheduled")} />}
  </div>;
}

function summaryOf(detail: ThanksDetail): ThanksSummary {
  const { recipients, ...summary } = detail;
  void recipients;
  return summary;
}

function PageHeader() {
  return <>
    <div className="mail-breadcrumb"><Link href="/">홈</Link><span>/</span><Link href="/follow-up/thank-you">행사별 후속 관리</Link><span>/</span><strong>감사 메일</strong></div>
    <div className="mail-page-header"><div><p className="eyebrow">FOLLOW-UP MAIL</p><h1>감사 메일</h1><p>행사 참석자에게 감사 인사와 행사 관련 안내를 전달합니다.</p></div><span className="mock-badge">승인 상태만 기록 · 실제 메일 미발송</span></div>
  </>;
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

function MailPreview({ recipients, excluded }: { recipients: ThanksRecipient[]; excluded: Set<string> }) {
  const [mode, setMode] = useState<"included" | "omitted">("included");
  const [email, setEmail] = useState("");
  const candidates = recipients.filter((item) => item.surveyIncluded === (mode === "included"));
  const person = candidates.find((item) => item.email === email) ?? candidates[0];
  const switchMode = (next: "included" | "omitted") => { setMode(next); setEmail(""); };
  const toolbar = <div className="preview-toolbar"><div className="preview-switch"><button className={mode === "included" ? "active" : ""} type="button" onClick={() => switchMode("included")}>설문 요청 포함</button><button className={mode === "omitted" ? "active" : ""} type="button" onClick={() => switchMode("omitted")}>설문 요청 미포함</button></div>{candidates.length > 0 && <div className="select-wrap"><select value={person?.email ?? ""} onChange={(e) => setEmail(e.target.value)} aria-label="미리볼 받는 사람">{candidates.map((item) => <option key={item.email} value={item.email}>{item.name} · {item.email}{excluded.has(item.email) ? " (제외)" : ""}</option>)}</select><ChevronDown size={15} /></div>}</div>;
  if (!person) return <div className="mail-preview">{toolbar}<EmptyState message={recipients.length ? "해당 유형의 받는 사람이 없습니다." : "메일 초안이 없어 미리보기를 표시할 수 없습니다."} /></div>;
  return <div className="mail-preview">{toolbar}<div className="preview-meta"><span>발신자</span><strong>{person.sender}</strong><span>수신자</span><strong>{person.email}</strong><span>제목</span><strong>{person.subject}</strong></div><pre>{renderPreviewBody(person.body)}</pre>{excluded.has(person.email) && <p className="preview-note">이 받는 사람은 발송 대상에서 제외되어 있습니다.</p>}{person.approvalInvalid && <p className="preview-note">승인 후 내용이 바뀌어 다시 승인이 필요해요.</p>}</div>;
}

function SendConfirmationDialog({ type, status, count, schedule, busy, onClose, onConfirm }: { type: "immediate" | "scheduled"; status: ThanksSummary["status"]; count: number; schedule: Schedule; busy: boolean; onClose: () => void; onConfirm: () => void }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);
  if (typeof document === "undefined") return null;
  const immediate = type === "immediate";
  return createPortal(<div className="modal-backdrop confirmation-backdrop" role="presentation"><div className="send-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="send-confirm-title"><div className="send-confirm-icon"><Send size={20} /></div><h2 id="send-confirm-title">{immediate ? "감사 메일 즉시 발송" : "감사 메일 예약 발송 승인"}</h2>{immediate ? <><p>최종 발송 대상 <strong>{count}명</strong>에게 감사 메일을 지금 발송하시겠습니까?</p><p className="send-confirm-warning">발송이 완료되면 취소할 수 없습니다. (실제 메일은 보내지 않고 발송 상태만 기록합니다.)</p>{status === "scheduled" && <p className="send-confirm-warning">현재 예약 발송은 즉시 발송으로 대체됩니다.</p>}</> : <><p>다음 일정에 감사 메일을 발송하도록 승인하시겠습니까?</p><dl className="send-confirm-facts"><dt>발송 대상</dt><dd>{count}명</dd><dt>발송 예정일</dt><dd>{schedule.date}</dd><dt>발송 예정 시간</dt><dd>{schedule.time} (Asia/Seoul)</dd></dl><p className="send-confirm-note">예약 발송은 발송 예정 시각 전까지 변경하거나 취소할 수 있습니다.</p></>}<div className="send-confirm-actions"><button className="secondary-button" type="button" onClick={onClose} disabled={busy}>취소</button><button className="primary-button" type="button" onClick={onConfirm} disabled={busy}>{busy ? "처리 중..." : immediate ? <><Send size={15} /> 지금 발송</> : <><CalendarCheck size={15} /> 예약 발송 승인</>}</button></div></div></div>, document.body);
}

const APPROVAL_LABEL: Record<ThanksApprovalStatus, string> = { none: "미승인", scheduled: "예약", sent: "발송", excluded: "제외" };

function RecipientEditorDialog({ eventName, recipients, initialExcluded, readOnly, onClose, onApply }: { eventName: string; recipients: ThanksRecipient[]; initialExcluded: Set<string>; readOnly: boolean; onClose: () => void; onApply: (excluded: Set<string>) => void }) {
  const [excluded, setExcluded] = useState(() => new Set(initialExcluded));
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<RecipientFilter>("all");
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const filtered = recipients.filter((person) => {
    const matchesQuery = [person.name, person.company, person.title, person.email].some((value) => (value ?? "").toLowerCase().includes(query.toLowerCase()));
    const included = !excluded.has(person.email);
    return matchesQuery && (filter === "all" || (filter === "included" && included) || (filter === "excluded" && !included));
  });
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const finalCount = recipients.filter((person) => !excluded.has(person.email)).length;
  const toggle = (email: string) => setExcluded((current) => { const next = new Set(current); if (next.has(email)) next.delete(email); else next.add(email); return next; });
  const allFilteredIncluded = filtered.length > 0 && filtered.every((person) => !excluded.has(person.email));
  const toggleFiltered = () => setExcluded((current) => { const next = new Set(current); filtered.forEach((person) => allFilteredIncluded ? next.add(person.email) : next.delete(person.email)); return next; });
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  if (typeof document === "undefined") return null;

  return createPortal(<div className="modal-backdrop" role="presentation"><div className="recipient-modal" role="dialog" aria-modal="true" aria-label="발송 대상 편집"><div className="modal-header"><div><p className="eyebrow">RECIPIENTS</p><h2>발송 대상 편집</h2><p>{eventName} · 메일 초안 {recipients.length}명{readOnly ? " · 발송 완료(보기 전용)" : ""}</p></div><button className="icon-button" onClick={onClose} type="button" aria-label="닫기"><X size={20} /></button></div><div className="modal-summary"><Metric label="기본 대상" value={`${recipients.length}명`} /><Metric label="제외 대상" value={`${excluded.size}명`} /><Metric label="설문 요청 포함" value={`${recipients.filter((person) => person.surveyIncluded && !excluded.has(person.email)).length}명`} /><Metric label="최종 발송" value={`${finalCount}명`} accent /></div><div className="modal-toolbar"><div className="search-input"><Search size={16} /><input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="이름, 회사, 직함, 이메일 검색" /></div><div className="filter-tabs">{(["all", "included", "excluded"] as RecipientFilter[]).map((item) => <button className={filter === item ? "active" : ""} key={item} onClick={() => { setFilter(item); setPage(1); }} type="button">{{ all: "전체 대상", included: "발송 대상", excluded: "제외 대상" }[item]}</button>)}</div><button className="secondary-button" type="button" disabled title="데이터 관리에서 등록 기능 준비 중"><UserPlus size={15} /> 참석자 추가</button></div><p className="template-help">누락된 참석자 직접 등록: 데이터 관리에서 등록 기능 준비 중입니다.</p><div className="recipient-table-wrap"><table className="recipient-table"><thead><tr><th><input type="checkbox" checked={allFilteredIncluded} onChange={toggleFiltered} disabled={readOnly} aria-label="현재 결과 전체 선택" /></th><th>이름</th><th>회사</th><th>직함</th><th>이메일</th><th>설문 요청</th><th>승인 상태</th></tr></thead><tbody>{visible.map((person) => { const included = !excluded.has(person.email); return <tr key={person.draftId} className={!included ? "excluded-row" : ""}><td><input type="checkbox" checked={included} onChange={() => toggle(person.email)} disabled={readOnly} aria-label={`${person.name} 발송 대상`} /></td><td>{person.name}</td><td>{person.company || "미등록"}</td><td>{person.title || "미등록"}</td><td className="email-cell">{person.email}</td><td><span className={`survey-dot ${person.surveyIncluded ? "unanswered" : "answered"}`}>{person.surveyIncluded ? "포함" : "미포함"}</span></td><td>{APPROVAL_LABEL[person.approvalStatus]}{person.approvalInvalid ? " · 다시 승인 필요" : ""}</td></tr>; })}</tbody></table>{visible.length === 0 && <EmptyState message="조건에 맞는 대상이 없습니다." />}</div><div className="pagination"><span>전체 {filtered.length}명 중 {filtered.length ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, filtered.length)}` : "0"}명</span><div><select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} aria-label="페이지당 표시 수"><option value="10">10명</option><option value="20">20명</option><option value="50">50명</option></select><button className="page-button" disabled={page <= 1} onClick={() => setPage(page - 1)} type="button"><ChevronLeft size={15} /></button><span>{page} / {pageCount}</span><button className="page-button" disabled={page >= pageCount} onClick={() => setPage(page + 1)} type="button"><ChevronRight size={15} /></button></div></div><div className="modal-footer"><strong>최종 발송 대상 {finalCount}명</strong><div><button className="text-button" type="button" onClick={() => setExcluded(new Set())} disabled={readOnly}>전체 복원</button><button className="secondary-button" type="button" onClick={onClose}>취소</button><button className="primary-button" type="button" onClick={() => onApply(excluded)} disabled={readOnly}>적용</button></div></div></div></div>, document.body);
}
