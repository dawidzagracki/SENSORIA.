import type { Metadata } from "next";
import { ContentPageView } from "@/components/content/content-page-view";
import { getContentPage } from "@/lib/content-api";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const page = await getContentPage("regulamin");
  return {
    title: "Regulamin | SENSORIA",
    description:
      page?.summary ??
      "Regulamin sklepu Sensoria: zasady zakupów, płatności, dostawy i odstąpienia od umowy.",
    robots: page ? undefined : { index: false, follow: true },
  };
}

export default async function Page() {
  return (
    <ContentPageView
      page={await getContentPage("regulamin")}
      fallbackTitle="Regulamin"
    />
  );
}
