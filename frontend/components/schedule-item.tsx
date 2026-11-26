import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { ScheduleItem as ScheduleItemData } from "@/lib/dashboard-data";
import { formatScheduleDate } from "@/lib/dashboard-data";
import { StatusText } from "@/components/status-text";

export function ScheduleItem({ item }: { item: ScheduleItemData }) {
  const date = formatScheduleDate(item.date);
  return <Link className="schedule-row" href={item.href}><div className="date-box"><span>{date.month}</span><strong>{date.day}</strong></div><div className="schedule-copy"><strong>{item.title}</strong><span>{item.detail}</span></div><StatusText tone={item.tone}>{item.status}</StatusText><ArrowUpRight className="schedule-arrow" size={17} /></Link>;
}
