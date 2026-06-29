import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AURORA — Enterprise Decision Intelligence OS",
  description:
    "A living digital twin of your company: see everything, model the business, connect the dots, and decide.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-base text-text-primary font-sans antialiased">{children}</body>
    </html>
  );
}
