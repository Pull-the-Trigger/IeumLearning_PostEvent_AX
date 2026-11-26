import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export function SectionHeader({ title, description, href }: { title: string; description?: string; href?: string }) {
  return <div className="section-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{href && <Link className="text-link" href={href}>전체 보기 <ArrowUpRight size={15} /></Link>}</div>;
}
