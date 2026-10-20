import type { Metadata } from "next";
import { ContentPageView } from "@/components/content/content-page-view";
import { getContentPage } from "@/lib/content-api";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const page = await getContentPage("polityka-prywatnosci");
  return {
    title: "Polityka prywatności | SENSORIA",
    description:
      page?.summary ??
      "Jak przetwarzamy dane osobowe klientek sklepu Sensoria.",
    robots: page ? undefined : { index: false, follow: true },
  };
}

export default async function Page() {
  return (
    <ContentPageView
      page={await getContentPage("polityka-prywatnosci")}
      fallbackTitle="Polityka prywatności"
    />
  );
}
