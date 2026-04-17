import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Analyst Agent",
  description: "AI-powered data analysis workbench for multi-table business questions"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
