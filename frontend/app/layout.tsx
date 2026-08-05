import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";

import { ConfirmDialogProvider } from "@/components/feedback/ConfirmDialog";
import { ToastProvider } from "@/components/feedback/ToastProvider";
import AppShell from "@/components/shell/AppShell";
import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ContractOps AI",
  description: "منصة عمليات العقود بالذكاء الاصطناعي — جميع القطاعات",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html dir="rtl" lang="ar">
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
