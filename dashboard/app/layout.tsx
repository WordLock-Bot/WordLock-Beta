import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "WordLock",
  description:
    "WordLock — Automatische Wortfilterung, Beleidigungserkennung und Community-Sicherheit für deinen Discord Server.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "WordLock",
    statusBarStyle: "black-translucent",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
