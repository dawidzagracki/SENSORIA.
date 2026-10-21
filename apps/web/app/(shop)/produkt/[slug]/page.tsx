import { permanentRedirect } from "next/navigation";

type Props = { params: Promise<{ slug: string }> };

/** Legacy address: every product lives at /sklep/{slug} (one canonical URL). */
export default async function LegacyProductPage({ params }: Props) {
  const { slug } = await params;
  permanentRedirect(`/sklep/${encodeURIComponent(slug)}`);
}
