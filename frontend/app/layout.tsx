import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";

import Header from "@/components/Header";
import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ContractOps AI",
  description: "إدارة عقود الباطن بالذكاء الاصطناعي",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html dir="rtl" lang="ar">
      <body className={plex.className}>
        <I18nProvider>
          <Header />
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        </I18nProvider>
      </body>
    </html>
  );
}
