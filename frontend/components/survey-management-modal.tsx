"use client";

import { createPortal } from "react-dom";
import { useEffect, useMemo, useState } from "react";
import { BarChart3, Check, Clipboard, Download, ExternalLink, FileSpreadsheet, QrCode, Search, X } from "lucide-react";
import * as QRCode from "qrcode";
import * as XLSX from "xlsx";
import { EmptyState } from "@/components/empty-state";
import { StatusText } from "@/components/status-text";
import type { CustomerProfile, ThankYouEvent } from "@/lib/thank-you-mail-data";
import { normalizeEmail } from "@/lib/thank-you-mail-data";
import { readSurveyResponses, surveyTemplate, type SurveyDefinition, type SurveyResponse } from "@/lib/survey-data";

/* QR data URLs are intentionally rendered as native images so the same data URL can be downloaded. */
/* eslint-disable @next/next/no-img-element */

type IdentificationFilter = "all" | "identified" | "anonymous" | "unmatched";
type ResponseRow = SurveyResponse & { person?: CustomerProfile; identification: "identified" | "anonymous" | "unmatched" };

function safeCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return /^[=+\-@]/.test(text) ? `'${text}` : text;
}

function formatSubmittedAt(value: string) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short" }).format(date);
}

function getResponseRows(event: ThankYouEvent, definition: SurveyDefinition): ResponseRow[] {
  const peopleByEmail = new Map(event.recipients.filter((person) => person.email).map((person) => [normalizeEmail(person.email), person]));
  return readSurveyResponses().filter((response) => response.eventId === event.id && response.surveyId === definition.surveyId).map((response) => {
    const person = response.email ? peopleByEmail.get(normalizeEmail(response.email)) : undefined;
    const identification: ResponseRow["identification"] = person ? "identified" : response.email ? "unmatched" : "anonymous";
    return { ...response, person, identification };
  }).sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));
}

function calculateAverage(rows: ResponseRow[], id: string, max: number) {
  const values = rows.map((row) => Number(row.answers[id])).filter((value) => Number.isFinite(value) && value >= 0 && value <= max);
  return values.length ? { value: (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1), count: values.length, max } : null;
}

function SurveyManagementModalContent({ event, definition, publicUrl, onClose }: { event: ThankYouEvent; definition: SurveyDefinition; publicUrl: string; onClose: () => void }) {
  const [responses] = useState<ResponseRow[]>(() => getResponseRows(event, definition));
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<IdentificationFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [copied, setCopied] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [qrOpen, setQrOpen] = useState(false);
  const [detail, setDetail] = useState<ResponseRow | null>(null);

  useEffect(() => {
    QRCode.toDataURL(publicUrl, { width: 420, margin: 2, errorCorrectionLevel: "M" }).then(setQrDataUrl).catch(() => setQrDataUrl(""));
  }, [publicUrl]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  const identifiedCount = responses.filter((row) => row.identification === "identified").length;
  const anonymousCount = responses.filter((row) => row.identification === "anonymous").length;
  const unmatchedCount = responses.filter((row) => row.identification === "unmatched").length;
  const responseCount = event.surveyCount || responses.length;
  const responseRate = event.attendedCount > 0 ? `${((responseCount / event.attendedCount) * 100).toFixed(1)}%` : "—";
  const averages = [calculateAverage(responses, "Q1", 5), calculateAverage(responses, "Q2", 5), calculateAverage(responses, "Q3", 10)];
  const filtered = useMemo(() => responses.filter((row) => {
    const haystack = [row.person?.name, row.person?.company, row.person?.title, row.email].filter(Boolean).join(" ").toLowerCase();
    return (!query || haystack.includes(query.toLowerCase())) && (filter === "all" || row.identification === filter);
  }), [filter, query, responses]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  async function copyLink() {
    await navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function downloadResponses() {
    const rows = responses.map((row) => ({
      "행사 ID": event.id,
      "행사명": event.name,
      "응답 ID": row.responseId,
      "응답 일시": formatSubmittedAt(row.submittedAt),
      "응답자 이름": row.person?.name ?? "",
      "회사명": row.person?.company ?? "",
      "직함": row.person?.title ?? "",
      "식별 여부": row.identification === "identified" ? "식별 완료" : row.identification === "anonymous" ? "익명" : "미매칭",
      "Q1 만족도": row.answers.Q1 ? Number(row.answers.Q1) : "",
      "Q2 도움 정도": row.answers.Q2 ? Number(row.answers.Q2) : "",
      "Q3 추천 의향": row.answers.Q3 ? Number(row.answers.Q3) : "",
      "Q4 도움이 된 내용": safeCell(row.answers.Q4),
      "Q5 듣고 싶은 주제": safeCell(row.answers.Q5),
      "Q6 도입 검토": safeCell(row.answers.Q6),
      "Q7 연락 희망": safeCell(row.answers.Q7),
      "Q8 이메일": safeCell(row.email),
    }));
    const sheet = XLSX.utils.json_to_sheet(rows);
    sheet["!cols"] = [{ wch: 16 }, { wch: 28 }, { wch: 28 }, { wch: 20 }, { wch: 16 }, { wch: 20 }, { wch: 14 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 34 }, { wch: 34 }, { wch: 16 }, { wch: 18 }, { wch: 32 }];
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, sheet, "만족도 응답");
    XLSX.writeFile(workbook, `${event.id}_${event.name.replace(/[\\/:*?"<>|]/g, "_")}_만족도조사_응답.xlsx`);
  }

  return <div className="modal-backdrop survey-management-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="survey-management-modal" role="dialog" aria-modal="true" aria-labelledby="survey-management-title"><div className="modal-header"><div><p className="eyebrow">SURVEY MANAGEMENT</p><h2 id="survey-management-title">만족도 조사 관리</h2><p>{event.name}</p></div><button className="icon-button" type="button" onClick={onClose} aria-label="닫기"><X size={20} /></button></div><div className="survey-management-body"><section className="survey-admin-section"><div className="survey-admin-heading"><div><span className="card-kicker">01</span><h3>설문 배포</h3></div><StatusText tone={definition.status === "open" ? "complete" : "muted"}>{definition.status === "open" ? "운영 중" : "종료"}</StatusText></div><div className="survey-distribution-card"><div className="survey-distribution-url"><span>참가자용 설문 URL</span><code title={publicUrl}>{publicUrl}</code></div><div className="survey-admin-actions"><button className="secondary-button" type="button" onClick={copyLink}>{copied ? <Check size={15} /> : <Clipboard size={15} />}{copied ? "복사됨" : "링크 복사"}</button><button className="secondary-button" type="button" onClick={() => setQrOpen(true)} disabled={!qrDataUrl}><QrCode size={15} /> QR코드 확인</button>{qrDataUrl && <a className="secondary-button" href={qrDataUrl} download={`${event.id}_설문_QR.png`}><Download size={15} /> QR 다운로드</a>}<a className="secondary-button" href={`/survey/preview/${definition.token}`} target="_blank" rel="noreferrer"><ExternalLink size={15} /> 설문 미리보기</a></div><small>로컬 환경의 URL은 외부 참가자가 접근할 수 없습니다. 배포 환경에서는 공개 도메인으로 생성됩니다.</small></div></section><section className="survey-admin-section"><div className="survey-admin-heading"><div><span className="card-kicker">02</span><h3>응답 수집 현황</h3></div></div><div className="survey-admin-metrics"><Metric label="전체 참석자" value={`${event.attendedCount}명`} /><Metric label="전체 설문 응답" value={`${responseCount}건`} /><Metric label="이메일 식별 응답" value={`${event.surveyIdentifiedCount || identifiedCount}건`} /><Metric label="익명 응답" value={`${event.surveyAnonymousCount || anonymousCount}건`} /><Metric label="설문 응답률" value={responseRate} /></div>{unmatchedCount > 0 && <p className="survey-admin-note">제출 이메일은 있으나 행사 참가자와 연결되지 않은 미매칭 응답 {unmatchedCount}건이 있습니다.</p>}</section><section className="survey-admin-section"><div className="survey-admin-heading"><div><span className="card-kicker">03</span><h3>설문 점수 요약</h3></div><a className="secondary-button" href={`/sales/event-performance?eventId=${encodeURIComponent(event.id)}`}><BarChart3 size={15} /> 상세 성과 확인</a></div><div className="survey-score-grid">{[{ label: "전반적인 행사 만족도", average: averages[0] }, { label: "업무 도움 정도", average: averages[1] }, { label: "동료 추천 의향", average: averages[2] }].map((item) => <div className="survey-score-card" key={item.label}><span>{item.label}</span><strong>{item.average ? `${item.average.value} / ${item.average.max}점` : "—"}</strong><div className="score-bar"><span style={{ width: item.average ? `${(Number(item.average.value) / item.average.max) * 100}%` : "0%" }} /></div><small>{item.average ? `유효 응답 ${item.average.count}건` : "확인 가능한 원문 응답 없음"}</small></div>)}</div></section><section className="survey-admin-section survey-response-section"><div className="survey-admin-heading"><div><span className="card-kicker">04</span><h3>설문 응답 목록</h3></div><button className="secondary-button" type="button" onClick={downloadResponses}><FileSpreadsheet size={15} /> 응답 엑셀 다운로드</button></div><div className="survey-response-toolbar"><label className="search-input"><Search size={16} /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="이름, 회사명, 이메일 검색" /></label><div className="filter-tabs">{([{ id: "all", label: "전체 응답" }, { id: "identified", label: "이메일 식별 응답" }, { id: "anonymous", label: "익명 응답" }, ...(unmatchedCount ? [{ id: "unmatched", label: "미매칭 응답" }] : [])] as { id: IdentificationFilter; label: string }[]).map((item) => <button className={filter === item.id ? "active" : ""} type="button" key={item.id} onClick={() => { setFilter(item.id); setPage(1); }}>{item.label}</button>)}</div></div><div className="survey-response-table-wrap"><table className="recipient-table survey-response-table"><thead><tr><th>번호</th><th>응답자</th><th>회사명</th><th>직함</th><th>만족도</th><th>업무 도움</th><th>추천 의향</th><th>식별 여부</th><th>응답 일시</th><th>상세</th></tr></thead><tbody>{visible.map((row, index) => <tr key={row.responseId}><td>{(page - 1) * pageSize + index + 1}</td><td>{row.person?.name ?? (row.identification === "unmatched" ? row.email : "익명 응답")}</td><td>{row.person?.company ?? "—"}</td><td>{row.person?.title ?? "—"}</td><td>{row.answers.Q1 ? `${row.answers.Q1} / 5` : "—"}</td><td>{row.answers.Q2 ? `${row.answers.Q2} / 5` : "—"}</td><td>{row.answers.Q3 ? `${row.answers.Q3} / 10` : "—"}</td><td><span className={`survey-identification ${row.identification}`}>{row.identification === "identified" ? "식별 완료" : row.identification === "unmatched" ? "미매칭" : "익명"}</span></td><td>{formatSubmittedAt(row.submittedAt)}</td><td><button className="text-button" type="button" onClick={() => setDetail(row)}>보기</button></td></tr>)}</tbody></table>{visible.length === 0 && <EmptyState message="조건에 맞는 설문 응답이 없습니다." />}</div><div className="pagination survey-response-pagination"><span>전체 {responses.length}건 중 {filtered.length ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, filtered.length)}` : "0"}건</span><div><select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} aria-label="페이지당 표시 수"><option value="10">10건</option><option value="20">20건</option><option value="50">50건</option></select><button className="page-button" type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button><span>{page} / {pageCount}</span><button className="page-button" type="button" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>›</button></div></div></section></div><div className="modal-footer"><strong>{event.name} · 응답 {responseCount}건</strong><button className="secondary-button" type="button" onClick={onClose}>닫기</button></div></div>{qrOpen && <div className="modal-backdrop survey-qr-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setQrOpen(false); }}><div className="survey-qr-modal" role="dialog" aria-modal="true" aria-label="설문 QR코드"><div className="modal-header"><div><h2>설문 QR코드</h2><p>{event.name}</p></div><button className="icon-button" type="button" onClick={() => setQrOpen(false)} aria-label="QR코드 닫기"><X size={20} /></button></div>{qrDataUrl ? <img src={qrDataUrl} alt={`${event.name} 참가자용 설문 QR코드`} /> : <EmptyState message="QR코드를 생성할 수 없습니다." />}<a className="primary-button" href={qrDataUrl} download={`${event.id}_설문_QR.png`}><Download size={15} /> PNG 다운로드</a></div></div>}{detail && <SurveyResponseDetail response={detail} event={event} onClose={() => setDetail(null)} />}</div>;
}

export function SurveyManagementModal(props: { event: ThankYouEvent; definition: SurveyDefinition; publicUrl: string; onClose: () => void }) {
  if (typeof document === "undefined") return null;
  return createPortal(<SurveyManagementModalContent {...props} />, document.body);
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="survey-admin-metric"><span>{label}</span><strong>{value}</strong></div>; }

function SurveyResponseDetail({ response, event, onClose }: { response: ResponseRow; event: ThankYouEvent; onClose: () => void }) {
  return <div className="modal-backdrop survey-detail-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="survey-detail-modal" role="dialog" aria-modal="true" aria-label="설문 응답 상세"><div className="modal-header"><div><p className="eyebrow">SURVEY RESPONSE</p><h2>설문 응답 상세</h2><p>{event.name}</p></div><button className="icon-button" type="button" onClick={onClose} aria-label="상세 닫기"><X size={20} /></button></div><div className="survey-detail-content"><div className="survey-detail-person"><span>응답자</span><strong>{response.person?.name ?? (response.identification === "unmatched" ? response.email : "익명 응답")}</strong>{response.person && <><span>회사명</span><strong>{response.person.company || "—"}</strong><span>직함</span><strong>{response.person.title || "—"}</strong></>}{response.email && <><span>이메일</span><strong>{response.email}</strong></>}<span>응답 일시</span><strong>{formatSubmittedAt(response.submittedAt)}</strong><span>식별 여부</span><strong>{response.identification === "identified" ? "식별 완료" : response.identification === "unmatched" ? "미매칭" : "익명"}</strong></div><div className="survey-detail-answers">{surveyTemplate.questions.map((question) => <div className="survey-detail-answer" key={question.id}><div><span>{question.id}</span><strong>{question.text}</strong></div>{question.id === "Q1" || question.id === "Q2" || question.id === "Q3" ? <><b>{response.answers[question.id] || "미응답"} / {question.id === "Q3" ? 10 : 5}점</b><div className="score-bar"><span style={{ width: response.answers[question.id] ? `${(Number(response.answers[question.id]) / (question.id === "Q3" ? 10 : 5)) * 100}%` : "0%" }} /></div></> : <p>{response.answers[question.id] || "미입력"}</p>}</div>)}</div></div><div className="modal-footer"><button className="secondary-button" type="button" onClick={onClose}>닫기</button></div></div></div>;
}
