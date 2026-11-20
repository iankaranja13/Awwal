import type { Metadata, Viewport } from "next";
import { Readex_Pro } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const readex = Readex_Pro({
  subsets: ["latin"],
  variable: "--font-readex",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Awwal",
  description: "A private first step for men's reproductive health. Prototype.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#edf0ec",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" className={readex.variable} suppressHydrationWarning>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
