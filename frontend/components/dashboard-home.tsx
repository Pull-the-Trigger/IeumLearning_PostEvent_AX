import { CalendarClock } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { EventFollowupCard } from "@/components/event-followup-card";
import { SectionHeader } from "@/components/section-header";
import { ScheduleItem } from "@/components/schedule-item";
import { TaskSummaryCard } from "@/components/task-summary-card";
import { demoDate, getKoreanToday, getSortedSchedules, getVisibleEvents, followupEvents, schedules, taskGroups } from "@/lib/dashboard-data";

export function DashboardHome() {
  const events = getVisibleEvents(followupEvents);
  const upcoming = getSortedSchedules(schedules, demoDate);
  return <div className="dashboard-page"><div className="page-header"><div><p className="eyebrow">MARKETING OPERATIONS</p><h1>업무 대시보드</h1><p className="page-date">{getKoreanToday()}</p></div><div className="demo-badge">데모 기준일 · 2026년 11월 25일</div></div><section><SectionHeader title="처리 대기 업무" description="현재 검토와 확인이 필요한 업무를 한눈에 확인하세요." /><div className="task-grid">{taskGroups.map((group) => <TaskSummaryCard group={group} key={group.groupId} />)}</div></section><section><SectionHeader title="행사별 후속 관리 현황" description="후속 관리 진행 중인 행사 · 최대 3개 표시" href="/data/events" /><div className="event-list">{events.length ? events.map((event) => <EventFollowupCard event={event} key={event.id} />) : <EmptyState message="현재 후속 관리가 필요한 행사가 없습니다." />}</div></section><section><SectionHeader title="다가오는 업무 일정" description="완료되지 않은 일정은 기한이 지나도 목록에서 유지됩니다." /><div className="schedule-card"><div className="schedule-card-title"><CalendarClock size={18} /><span>예정된 업무</span></div>{upcoming.length ? upcoming.map((item) => <ScheduleItem item={item} key={`${item.date}-${item.title}`} />) : <EmptyState message="예정된 업무 일정이 없습니다." />}</div></section></div>;
}
