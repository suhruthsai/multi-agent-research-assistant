"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { GitCompare } from "lucide-react";

interface Props {
  markdown: string;
  paperCount: number;
}

export default function ComparativeAnalysis({ markdown, paperCount }: Props) {
  if (!markdown || markdown.trim() === "") return null;

  return (
    <div className="glass-card overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-gray-800/40 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center">
          <GitCompare className="w-4 h-4 text-cyan-400" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white">Comparative Analysis</h2>
          <p className="text-[11px] text-gray-500 mt-0.5">
            Cross-paper analysis of {paperCount} paper{paperCount !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-[10px] text-cyan-400 font-medium">AI Generated</span>
        </div>
      </div>

      {/* Markdown body */}
      <div className="px-5 pb-6 pt-4 report-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}
