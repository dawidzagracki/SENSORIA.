import type { Metadata } from "next";
import { AdminProductEdit } from "@/components/admin/products";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Edycja produktu | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AdminProductEdit id={id} />;
}
