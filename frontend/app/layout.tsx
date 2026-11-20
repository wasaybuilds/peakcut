import type { Metadata } from "next";
import { Big_Shoulders } from "next/font/google";
import "./globals.css";

import { Shell } from "@/components/shell";

// One condensed family; the optical-size axis carries both letterboard titles and UI text.
const shoulders = Big_Shoulders({ variable: "--font-shoulders", subsets: ["latin"], axes: ["opsz"] });

export const metadata: Metadata = {
  title: "PeakCut",
  description: "Turn long YouTube videos into ready-to-post Shorts and Reels with free AI.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={shoulders.variable}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
