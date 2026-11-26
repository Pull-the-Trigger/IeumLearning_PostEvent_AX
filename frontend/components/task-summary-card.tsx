import Link from "next/link";
import type { TaskGroup } from "@/lib/dashboard-data";
import { StatusText } from "@/components/status-text";
import { getNavigationGroup } from "@/lib/navigation";

export function TaskSummaryCard({ group }: { group: TaskGroup }) {
  const menuGroup = getNavigationGroup(group.groupId);
  const Icon = menuGroup.icon;
  return <article className="task-card"><div className="task-card-heading"><span className="task-icon"><Icon size={19} /></span><h3>{menuGroup.label}</h3></div><div className="task-list">{group.items.map((item) => <Link className="task-row" href={item.href} key={`${menuGroup.id}-${item.label}`}><span>{item.label}</span><StatusText tone={item.tone ?? "pending"}>{item.count}</StatusText></Link>)}</div></article>;
}
