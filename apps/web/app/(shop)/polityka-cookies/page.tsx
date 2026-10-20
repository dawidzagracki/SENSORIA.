import type { Metadata } from "next";
import { ContentPageView } from "@/components/content/content-page-view";
import { getContentPage } from "@/lib/content-api";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const page = await getContentPage("polityka-cookies");
  return {
    title: "Polityka cookies | SENSORIA",
    description:
      page?.summary ??
      "Jakich plików cookies używamy i jak zmienić swój wybór.",
    robots: page ? undefined : { index: false, follow: true },
  };
}

export default async function Page() {
  return (
    <ContentPageView
      page={await getContentPage("polityka-cookies")}
      fallbackTitle="Polityka cookies"
    />
  );
}
