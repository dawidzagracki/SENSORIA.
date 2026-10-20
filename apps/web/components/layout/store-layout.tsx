import type { ReactNode } from "react";
import { AnnouncementBar } from "./announcement-bar";
import { CartCountProvider } from "./cart-count-provider";
import { readInitialCartSnapshot } from "./cart-adapter";
import { ShopFooter } from "./shop-footer";
import { ShopHeader } from "./shop-header";

export async function StoreLayout({ children }: { children: ReactNode }) {
  const cartSnapshot = await readInitialCartSnapshot();
  const demoEnabled = process.env.ENVIRONMENT === "development";

  return (
    <CartCountProvider initialSnapshot={cartSnapshot}>
      <AnnouncementBar />
      <ShopHeader />
      {children}
      <ShopFooter demoEnabled={demoEnabled} />
    </CartCountProvider>
  );
}
