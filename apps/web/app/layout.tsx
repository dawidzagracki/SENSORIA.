import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Sensoria Shop",
    template: "%s | Sensoria Shop",
  },
  description: "Szkielet aplikacji Sensoria Shop.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pl">
      <body>
        <a className="skip-link" href="#main-content">
          Przejdź do treści
        </a>
        {children}
      </body>
    </html>
  );
}
