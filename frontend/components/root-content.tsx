"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/app-shell";

export function RootContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicSurvey = pathname.startsWith("/survey/");
  return isPublicSurvey ? <>{children}</> : <AppShell>{children}</AppShell>;
}
