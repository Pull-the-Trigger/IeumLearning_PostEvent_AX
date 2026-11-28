import { BarChart3, BookOpen, CalendarDays, Database, FileText, HelpCircle, Home, Mail, Megaphone, MessageCircle, NotebookTabs, Presentation, Settings, Target, Users, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TaskMenuGroupId = "followUp" | "broadcast" | "requests" | "sales";
export type NavigationItem = { label: string; href: string; icon?: LucideIcon };
export type NavigationGroup = { id: string; label: string; icon: LucideIcon; items: NavigationItem[]; divider?: boolean; taskGroupId?: TaskMenuGroupId };

export const navigationGroups: NavigationGroup[] = [
  { id: "home", label: "홈", icon: Home, items: [{ label: "홈", href: "/" }] },
  { id: "followUp", label: "행사별 후속 관리", icon: Workflow, taskGroupId: "followUp", items: [{ label: "감사 메일", href: "/follow-up/thank-you", icon: Mail }, { label: "개인 맞춤 메일", href: "/follow-up/personal-mail", icon: MessageCircle }] },
  { id: "broadcast", label: "정기 발송", icon: Megaphone, taskGroupId: "broadcast", items: [{ label: "뉴스레터", href: "/broadcast/newsletter", icon: NotebookTabs }, { label: "개인 맞춤 콘텐츠", href: "/broadcast/personal-content", icon: BookOpen }] },
  { id: "requests", label: "고객 질문 및 요청 처리", icon: HelpCircle, taskGroupId: "requests", items: [{ label: "문의 답변", href: "/requests/replies", icon: MessageCircle }, { label: "부서 협업 관리", href: "/requests/collaboration", icon: Workflow }] },
  { id: "sales", label: "행사 성과 확인 & 영업 관리", icon: BarChart3, taskGroupId: "sales", items: [{ label: "행사 성과 확인", href: "/sales/event-performance", icon: Presentation }, { label: "영업 관리", href: "/sales/pipeline", icon: Target }] },
  { id: "data", label: "데이터 관리", icon: Database, divider: true, items: [{ label: "행사 정보", href: "/data/events", icon: CalendarDays }, { label: "참가자 및 고객 정보", href: "/data/people", icon: Users }, { label: "콘텐츠 및 자료", href: "/data/content", icon: FileText }] },
  { id: "settings", label: "설정", icon: Settings, divider: true, items: [{ label: "설정", href: "/settings", icon: Settings }] },
];

export function getNavigationGroup(id: TaskMenuGroupId) {
  return navigationGroups.find((group) => group.taskGroupId === id)!;
}
