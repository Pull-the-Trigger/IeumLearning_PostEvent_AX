"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navigationGroups } from "@/lib/navigation";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <nav aria-label="주 메뉴">
        {navigationGroups.map((group) => {
          const GroupIcon = group.icon;
          return <div className={`menu-group${group.divider ? " menu-group-divider" : ""}`} key={group.label}>
            <div className="menu-group-label"><GroupIcon size={16} /><span>{group.label}</span></div>
            {group.items?.map((item) => {
              const ItemIcon = item.icon;
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return <Link className={`menu-item${active ? " active" : ""}`} href={item.href} key={item.href}>
                {ItemIcon ? <ItemIcon size={15} /> : <span className="menu-dot" />}
                <span>{item.label}</span>
              </Link>;
            })}
          </div>;
        })}
      </nav>
    </aside>
  );
}
