"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, ClipboardCheck, Mail } from "lucide-react";
import { saveSurveyResponse, SurveyDefinition, surveyTemplate } from "@/lib/survey-data";

const scaleAnchors: Record<string, { left: string; right: string }> = {
  Q1: { left: "매우 불만족", right: "매우 만족" },
  Q2: { left: "전혀 도움이 되지 않음", right: "매우 도움이 됨" },
  Q3: { left: "전혀 추천하지 않음", right: "매우 추천함" },
};

export function SurveyForm({ definition, preview = false }: { definition: SurveyDefinition; preview?: boolean }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function update(id: string, value: string) {
    setAnswers((current) => ({ ...current, [id]: value }));
    setError("");
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (preview || submitting || submitted) return;
    const missing = surveyTemplate.questions.find((question) => question.required && !answers[question.id]?.trim());
    if (missing) {
      setError(`${missing.id} 문항에 응답해 주세요.`);
      document.getElementById(missing.id)?.focus();
      return;
    }
    setSubmitting(true);
    const email = answers.Q8?.trim();
    saveSurveyResponse({
      responseId: `${definition.surveyId}-${Date.now()}`,
      eventId: definition.eventId,
      surveyId: definition.surveyId,
      submittedAt: new Date().toISOString(),
      answers,
      email: email || undefined,
      customerLinkKey: email ? `${definition.eventId}:${email.toLowerCase()}` : undefined,
      identified: Boolean(email),
      contactFollowUp: answers.Q7 === "예",
    });
    setSubmitted(true);
    setSubmitting(false);
  }

  if (submitted) return <div className="survey-shell"><div className="survey-success"><CheckCircle2 size={44} /><h1>응답이 제출되었습니다</h1><p>소중한 의견을 보내주셔서 감사합니다.</p></div></div>;

  return <main className="survey-shell">
    {preview && <div className="survey-preview-banner"><ClipboardCheck size={17} /> 관리자 미리보기 — 응답이 저장되지 않습니다</div>}
    <header className="survey-header"><span className="survey-brand"><ClipboardCheck size={22} /> 이음러닝 | 행사 만족도 조사</span><h1>{definition.eventName}</h1><p>행사에 대한 의견을 남겨 주세요.</p></header>
    <form className="survey-form" onSubmit={submit}>
      {surveyTemplate.questions.map((question) => <div className="survey-question" key={question.id} role="group" aria-labelledby={`${question.id}-title`}>
        <div className="survey-question-title" id={`${question.id}-title`}><span className="survey-question-number">{question.id}</span><span className="survey-question-text">{question.text}</span><em>{question.required ? "필수" : "선택"}</em></div>
        <div className="survey-question-input">
          {question.type === "scale" || question.type === "score" ? <div className={`survey-linear-scale survey-linear-scale-${question.id}`}><span className="survey-scale-anchor survey-scale-anchor-left">{scaleAnchors[question.id].left}</span><div className="survey-scale-options">{question.options?.map((option) => <label className="survey-scale-option" key={option}><span className="survey-scale-number">{option}</span><input id={`${question.id}-${option}`} type="radio" name={question.id} value={option} checked={answers[question.id] === option} onChange={(event) => update(question.id, event.target.value)} disabled={preview} /></label>)}</div><span className="survey-scale-anchor survey-scale-anchor-right">{scaleAnchors[question.id].right}</span></div> : question.type === "choice" ? <div className="survey-choice-list">{question.options?.map((option) => <label key={option}><input id={`${question.id}-${option}`} type="radio" name={question.id} value={option} checked={answers[question.id] === option} onChange={(event) => update(question.id, event.target.value)} disabled={preview} /><span>{option}</span></label>)}</div> : <label className="survey-text-field">{question.type === "email" && <Mail size={16} />}{question.type === "textarea" ? <textarea id={question.id} value={answers[question.id] ?? ""} onChange={(event) => update(question.id, event.target.value)} placeholder="내용을 입력해 주세요" disabled={preview} /> : <input id={question.id} type="email" value={answers[question.id] ?? ""} onChange={(event) => update(question.id, event.target.value)} placeholder="연락을 원하실 때 입력해 주세요" disabled={preview} />}</label>}
        </div>
        {question.id === "Q8" && <small className="survey-question-help">이메일을 입력하지 않으면 익명으로 저장됩니다.</small>}
      </div>)}
      {error && <p className="survey-error" role="alert">{error}</p>}
      <button className="survey-submit" type="submit" disabled={preview || submitting}>{preview ? "미리보기에서는 제출할 수 없습니다" : submitting ? "제출 중..." : "응답 제출"}</button>
    </form>
  </main>;
}
