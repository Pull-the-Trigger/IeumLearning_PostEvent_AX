"use client";

import { useState, useSyncExternalStore } from "react";
import { Clipboard, ExternalLink } from "lucide-react";
import { LEGACY_SURVEY_RESPONSE_COUNT, readSurveyResponses, surveyDefinitions } from "@/lib/survey-data";

export function SurveyManagementPage() {
  const [copied, setCopied] = useState("");
  const browserOrigin = useSyncExternalStore(() => () => undefined, () => window.location.origin, () => "");
  const responses = readSurveyResponses();
  const publicUrl = (definition: typeof surveyDefinitions[number]) => browserOrigin ? `${browserOrigin}/survey/${definition.token}` : `/survey/${definition.token}`;
  async function copy(definition: typeof surveyDefinitions[number]) {
    await navigator.clipboard.writeText(publicUrl(definition));
    setCopied(definition.eventId);
    window.setTimeout(() => setCopied(""), 1800);
  }
  return <div className="page-content"><div className="page-heading"><div><span className="eyebrow">DATA MANAGEMENT</span><h1>만족도 조사</h1><p>행사별 설문 링크와 응답 연결 상태를 확인합니다.</p></div></div><section className="management-card"><div className="management-card-header"><h2>행사별 설문 링크</h2><span className="muted-text">공통 템플릿 · 기존 원본 응답 {LEGACY_SURVEY_RESPONSE_COUNT}건 + 신규 로컬 응답 {responses.length}건</span></div><div className="survey-management-list">{surveyDefinitions.map((definition) => { const count = responses.filter((response) => response.eventId === definition.eventId).length; return <article className="survey-management-row" key={definition.eventId}><div><strong>{definition.eventName}</strong><small>{definition.surveyId} · {definition.status === "open" ? "운영 중" : "종료"} · 신규 응답 {count}건</small><code>{publicUrl(definition)}</code></div><div className="survey-management-actions"><button className="secondary-button" type="button" onClick={() => copy(definition)}><Clipboard size={15} />{copied === definition.eventId ? "복사됨" : "링크 복사"}</button><a className="secondary-button" href={`/survey/preview/${definition.token}`} target="_blank" rel="noreferrer"><ExternalLink size={15} />미리보기</a></div></article>; })}</div></section></div>;
}
