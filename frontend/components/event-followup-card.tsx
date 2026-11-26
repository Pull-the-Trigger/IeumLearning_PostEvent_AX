import Link from "next/link";
import { ArrowRight, CalendarDays } from "lucide-react";
import type { FollowupEvent } from "@/lib/dashboard-data";
import { StatusText } from "@/components/status-text";

export function EventFollowupCard({ event }: { event: FollowupEvent }) {
  const responseRate = ((event.survey.responseCount / event.attendees) * 100).toFixed(1);
  return <article className="event-card"><div className="event-card-header"><div className="event-title"><span className="event-icon"><CalendarDays size={18} /></span><div><h3>{event.name}</h3><p>참석자 {event.attendees}명</p></div></div><Link className="round-link" href={`/data/events/${event.id}`} aria-label={`${event.name} 상세 보기`}><ArrowRight size={17} /></Link></div><div className="event-metrics"><div><span className="metric-label">감사 메일</span><StatusText tone={event.thankYou.tone}>{event.thankYou.label}</StatusText></div><div><span className="metric-label">만족도 조사 응답</span><strong>{event.survey.responseCount}명 <em>({responseRate}%)</em></strong><StatusText tone={event.survey.tone}>{event.survey.status}</StatusText></div><div><span className="metric-label">개인 맞춤 메일</span><StatusText tone={event.personalMail.tone}>{event.personalMail.label}</StatusText></div></div></article>;
}
