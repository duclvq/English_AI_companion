import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "English AI Companion",
  description: "Learn English with AI-powered lessons",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-100 min-h-screen">
        <div className="max-w-md mx-auto min-h-screen bg-slate-50 shadow-xl">{children}</div>
      </body>
    </html>
  );
}
