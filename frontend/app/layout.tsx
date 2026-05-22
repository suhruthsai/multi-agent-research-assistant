import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MARA — Multi-Agent Research Assistant",
  description:
    "Autonomous AI-powered research assistant with 7 specialist agents, hybrid RAG, knowledge graphs, and fact-checking. Search 250M+ academic papers across Semantic Scholar, arXiv, OpenAlex, and CrossRef.",
  keywords: [
    "research assistant",
    "AI",
    "multi-agent",
    "academic search",
    "literature review",
    "RAG",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body className="bg-[#06080f] text-gray-100 antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
