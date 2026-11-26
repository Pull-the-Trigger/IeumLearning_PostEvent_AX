import { Bell, Layers, UserCircle } from "lucide-react";

export function Header() {
  return (
    <header className="top-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true"><Layers size={20} /></span>
        <span className="brand-name">이음러닝</span>
        <span className="brand-description">행사 후속 관리 시스템</span>
      </div>
      <div className="header-actions" aria-label="사용자 메뉴">
        <button className="icon-button" type="button" aria-label="알림"><Bell size={19} /></button>
        <button className="icon-button" type="button" aria-label="사용자 프로필"><UserCircle size={21} /></button>
      </div>
    </header>
  );
}
