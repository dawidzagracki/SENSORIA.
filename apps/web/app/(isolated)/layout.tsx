import type { ReactNode } from "react";

export default function IsolatedRouteLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
