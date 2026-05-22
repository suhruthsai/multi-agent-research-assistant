"use client";
import { useEffect, useCallback } from "react";
import { X, ExternalLink } from "lucide-react";

type Paper = {
  title: string;
  abstract: string;
  authors: string[];
  year: number;
  url: string;
  source: string;
  citation_count: number;
  relevance_score: number;
};

interface CitationSidebarProps {
  paper: Paper | null;
  onClose: () => void;
}

function SourceBadge({ source }: { source: string }) {
  const cls =
    source === "arxiv"
      ? "badge-arxiv"
      : source === "semantic_scholar"
      ? "badge-semantic_scholar"
      : source === "openalex"
      ? "badge-openalex"
      : source === "crossref"
      ? "badge-crossref"
      : "badge-unknown";
  return <span className={`badge ${cls}`}>{source.replace("_", " ")}</span>;
}

export default function CitationSidebar({ paper, onClose }: CitationSidebarProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (paper) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [paper, handleKeyDown]);

  if (!paper) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md animate-slide-in-right">
        <div className="h-full bg-gray-950 border-l border-gray-800/50 flex flex-col shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-800/50">
            <h3 className="text-sm font-semibold text-gray-300">Paper Details</h3>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Title */}
            <h2 className="text-lg font-bold text-gray-100 leading-snug">
              {paper.title}
            </h2>

            {/* Authors & Year */}
            <div className="space-y-1.5">
              <p className="text-sm text-gray-400">
                {paper.authors.join(", ")}
              </p>
              {paper.year > 0 && (
                <p className="text-xs text-gray-600">Published: {paper.year}</p>
              )}
            </div>

            {/* Source badge */}
            <div className="flex items-center gap-3">
              <SourceBadge source={paper.source} />
              {paper.citation_count > 0 && (
                <span className="text-xs text-gray-500">
                  📊 {paper.citation_count.toLocaleString()} citations
                </span>
              )}
            </div>

            {/* Relevance Score */}
            {paper.relevance_score > 0 && (
              <div>
                <div className="flex items-center justify-between text-[11px] text-gray-400 mb-1">
                  <span>Relevance Score</span>
                  <span className="font-mono">
                    {(paper.relevance_score * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${Math.min(paper.relevance_score * 100, 100)}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {/* Abstract */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Abstract
              </h4>
              <p className="text-sm text-gray-300 leading-relaxed">
                {paper.abstract || "No abstract available."}
              </p>
            </div>
          </div>

          {/* Footer */}
          {paper.url && (
            <div className="p-4 border-t border-gray-800/50">
              <a
                href={paper.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary w-full flex items-center justify-center gap-2 text-white text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                Open Paper
              </a>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
