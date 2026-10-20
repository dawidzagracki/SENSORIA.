import type { Metadata } from "next";
import { LibraryView } from "@/components/library/library-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Moja biblioteka | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
};

export default function LibraryPage() {
  return <LibraryView />;
}
