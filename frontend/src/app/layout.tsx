import type { Metadata, Viewport } from "next";
import { Geist, Playfair_Display } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { AskDomiDrawer } from "@/components/chat/AskDomiDrawer";
import { ChatProvider } from "@/state/chat";
import { CompareProvider } from "@/state/compare";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"], display: "swap" });
const display = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Domi: find a home, feel at home", template: "%s | Domi" },
  description:
    "Search homes in Austin, Dallas and Phoenix in plain words, explore them on a map, and understand the monthly numbers.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f3ea" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1a15" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="flex min-h-[100dvh] flex-col">
        <a
          href="#main"
          className="sr-only rounded-full bg-primary px-4 py-2 text-on-primary focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100]"
        >
          Skip to content
        </a>
        <CompareProvider>
          <ChatProvider>
            <SiteHeader />
            <main id="main" className="flex-1">
              {children}
            </main>
            <SiteFooter />
            <AskDomiDrawer />
          </ChatProvider>
        </CompareProvider>
      </body>
    </html>
  );
}
