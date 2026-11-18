import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ResearchNest — Research, thoughtfully.", template: "%s | ResearchNest" },
  description: "A personal research workspace for discovering and organizing academic papers. In English and Bangla."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <a className="skip-link" href="#main-content">Skip to content / মূল বিষয়বস্তুতে যান</a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
