import type { TaskMenuGroupId } from "@/lib/navigation";

export type StatusTone = "warning" | "pending" | "complete" | "muted" | "danger";
export type TaskItem = { label: string; count: string; tone?: StatusTone; href: string };
export type TaskGroup = { groupId: TaskMenuGroupId; items: TaskItem[] };
export type FollowupEvent = { id: string; name: string; attendees: number; heldAt: string; thankYou: { label: string; tone: StatusTone }; survey: { responseCount: number; status: string; tone: StatusTone }; personalMail: { label: string; tone: StatusTone }; deadlinePriority: number; complete: boolean };
export type ScheduleItem = { date: string; title: string; detail: string; status: string; tone: StatusTone; priority: number; completed?: boolean; href: string };

export const taskGroups: TaskGroup[] = [
  { groupId: "followUp", items: [{ label: "감사 메일", count: "2개 행사", href: "/follow-up/thank-you" }, { label: "개인 맞춤 메일", count: "17건", href: "/follow-up/personal-mail" }] },
  { groupId: "broadcast", items: [{ label: "뉴스레터", count: "1건", href: "/broadcast/newsletter" }, { label: "개인 맞춤 콘텐츠", count: "6건", href: "/broadcast/personal-content" }] },
  { groupId: "requests", items: [{ label: "문의 답변", count: "8건", href: "/requests/replies" }, { label: "부서 협업 관리", count: "2건", href: "/requests/collaboration" }] },
  { groupId: "sales", items: [{ label: "행사 성과 확인", count: "조회", href: "/sales/event-performance" }, { label: "영업 관리", count: "8명", href: "/sales/pipeline" }] },
];

export const followupEvents: FollowupEvent[] = [
  { id: "event-seoul-ceo", name: "CEO 인사이트 특강 · 서울", attendees: 80, heldAt: "2026-11-20", thankYou: { label: "자료 등록 필요", tone: "warning" }, survey: { responseCount: 14, status: "응답 수집 중", tone: "muted" }, personalMail: { label: "12건 검토 대기", tone: "pending" }, deadlinePriority: 2, complete: false },
  { id: "event-hr-ai", name: "HR 담당자 AI 특강", attendees: 45, heldAt: "2026-11-18", thankYou: { label: "검토 대기", tone: "pending" }, survey: { responseCount: 8, status: "응답 수집 중", tone: "muted" }, personalMail: { label: "5건 검토 대기", tone: "pending" }, deadlinePriority: 1, complete: false },
  { id: "event-builderthon", name: "AI 빌더톤 데모데이", attendees: 20, heldAt: "2026-11-15", thankYou: { label: "발송 완료", tone: "complete" }, survey: { responseCount: 4, status: "결과 확인 대기", tone: "pending" }, personalMail: { label: "발송 완료", tone: "complete" }, deadlinePriority: 0, complete: false },
];

export const schedules: ScheduleItem[] = [
  { date: "2026-11-25", title: "감사 메일 발송 기한", detail: "CEO 인사이트 특강 · 서울", status: "자료 등록 필요", tone: "warning", priority: 1, href: "/follow-up/thank-you" },
  { date: "2026-11-25", title: "개인 맞춤 메일 발송", detail: "CEO 인사이트 특강 · 서울", status: "검토 대기", tone: "pending", priority: 2, href: "/follow-up/personal-mail" },
  { date: "2026-11-26", title: "고객 문의 추가 답변 기한", detail: "AI 역량 진단 관련 문의", status: "답변 준비 중", tone: "muted", priority: 3, href: "/requests/replies" },
  { date: "2026-11-27", title: "개인 맞춤 콘텐츠 발송", detail: "정기 발송 대상 고객", status: "검토 대기", tone: "pending", priority: 2, href: "/broadcast/personal-content" },
  { date: "2026-11-30", title: "뉴스레터 발송", detail: "11월 뉴스레터", status: "검토 대기", tone: "pending", priority: 2, href: "/broadcast/newsletter" },
  { date: "2026-11-30", title: "신규 행사 개최", detail: "AI 교육 설명회", status: "개최 예정", tone: "muted", priority: 4, href: "/data/events" },
];

export const demoDate = "2026-11-25";
export function getKoreanToday() { return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric", weekday: "long" }).format(new Date()); }
export function formatScheduleDate(date: string) { const value = new Date(`${date}T00:00:00+09:00`); return { month: `${value.getMonth() + 1}월`, day: `${value.getDate()}` }; }
export function getVisibleEvents(events: FollowupEvent[]) { return events.filter((event) => !event.complete).sort((a, b) => b.deadlinePriority - a.deadlinePriority || b.heldAt.localeCompare(a.heldAt)).slice(0, 3); }
export function getSortedSchedules(items: ScheduleItem[], referenceDate = demoDate) { return items.filter((item) => !item.completed).sort((a, b) => { const overdueA = a.date < referenceDate ? 1 : 0; const overdueB = b.date < referenceDate ? 1 : 0; return overdueB - overdueA || a.date.localeCompare(b.date) || a.priority - b.priority; }); }
