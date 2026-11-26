import { notFound } from "next/navigation";
import { PlaceholderPage } from "@/components/placeholder-page";

export default async function PlaceholderRoute({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  if (slug.length === 0) notFound();

  return <PlaceholderPage path={`/${slug.join("/")}`} />;
}
