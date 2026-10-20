import type { Metadata } from "next";
import { ContentPageView } from "@/components/content/content-page-view";
import { getContentPage } from "@/lib/content-api";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const page = await getContentPage("o-autorce");
  return {
    title: "O autorce | SENSORIA",
    description:
      page?.summary ?? "Poznaj autorkę materiałów i gabinetu Sensoria.",
    robots: page ? undefined : { index: false, follow: true },
  };
}

export default async function Page() {
  return (
    <ContentPageView
      page={await getContentPage("o-autorce")}
      fallbackTitle="O autorce"
    />
  );
}
