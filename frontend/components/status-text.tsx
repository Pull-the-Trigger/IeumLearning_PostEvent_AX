import type { StatusTone } from "@/lib/dashboard-data";

export function StatusText({ children, tone }: { children: React.ReactNode; tone: StatusTone }) {
  return <span className={`status-text status-${tone}`}>{children}</span>;
}
