import type { Metadata } from "next";
import { ContentPageView } from "@/components/content/content-page-view";
import { InPostLogo, PaymentLogos, StripeLogo } from "@/components/brand/logos";
import { getContentPage } from "@/lib/content-api";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const page = await getContentPage("dostawa-i-platnosci");
  return {
    title: "Dostawa i płatności | SENSORIA",
    description:
      page?.summary ?? "Koszty i czas dostawy oraz dostępne metody płatności.",
    robots: page ? undefined : { index: false, follow: true },
  };
}

export default async function Page() {
  return (
    <ContentPageView
      page={await getContentPage("dostawa-i-platnosci")}
      fallbackTitle="Dostawa i płatności"
      accessory={
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-card border border-border bg-surface-muted p-4">
          <span className="flex flex-wrap items-center gap-2">
            <PaymentLogos />
            <StripeLogo />
          </span>
          <InPostLogo />
        </div>
      }
    />
  );
}
