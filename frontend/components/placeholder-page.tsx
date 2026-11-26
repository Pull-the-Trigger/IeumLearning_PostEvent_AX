import { Construction } from "lucide-react";

export function PlaceholderPage({ path }: { path: string }) {
  return <div className="placeholder-page"><span className="placeholder-icon"><Construction size={24} /></span><p className="eyebrow">COMING SOON</p><h1>{path === "/" ? "홈" : "페이지 준비 중"}</h1><p>이 페이지의 상세 기능은 후속 작업에서 구현할 예정입니다.</p></div>;
}
