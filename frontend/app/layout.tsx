import type { Metadata } from "next";
import { RootContent } from "@/components/root-content";
import "./globals.css";

export const metadata: Metadata = {
  title: "이음러닝 | 행사 후속 관리 시스템",
  description: "이음러닝 행사 후속 관리 업무 대시보드",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" data-theme="dark">
      <body>
        <RootContent>{children}</RootContent>
      </body>
    </html>
  );
}
