import type { Metadata } from "next";
import { Amiri, Cormorant_Garamond, IBM_Plex_Sans_Arabic } from "next/font/google";

import { ConfirmDialogProvider } from "@/components/feedback/ConfirmDialog";
import { ToastProvider } from "@/components/feedback/ToastProvider";
import AppShell from "@/components/shell/AppShell";
import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

/** UI face — everything that is read as interface. */
const plex = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ui",
});

/** Classical naskh, for the ميثاق wordmark and display headlines. */
const amiri = Amiri({
  subsets: ["arabic", "latin"],
  weight: ["400", "700"],
  variable: "--font-display",
});

/** Letterspaced caps for the Latin half of the lockup. */
const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-wordmark",
});

export const metadata: Metadata = {
  title: "ميثاق — MITHAQ",
  description: "منصة عمليات العقود بالذكاء الاصطناعي — جميع القطاعات",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html dir="rtl" lang="ar" className={`${plex.variable} ${amiri.variable} ${cormorant.variable}`}>
      <body className={plex.className}>
        <I18nProvider>
          <ToastProvider>
            <ConfirmDialogProvider>
              <AppShell>{children}</AppShell>
            </ConfirmDialogProvider>
          </ToastProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
