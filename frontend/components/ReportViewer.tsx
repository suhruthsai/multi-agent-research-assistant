"use client";
import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Copy,
  Check,
  Download,
  FileText,
  FlaskConical,
  BookOpen,
  Network,
  ExternalLink,
} from "lucide-react";

/* ── Types ────────────────────────────────────────────────────────────────── */
export type Paper = {
  title: string;
  abstract: string;
  authors: string[];
  year: number;
  url: string;
  source: string;
  citation_count: number;
  relevance_score: number;
};

export type Hypothesis = {
  hypothesis: string;
  justification: string;
  confidence: number;
  methodology_hint?: string;
};

export type GraphData = {
  nodes: { id: string; label: string; type: string; year?: number; citation_count?: number }[];
  links: { source: string; target: string; type: string }[];
  stats: {
    total_nodes: number;
    total_edges: number;
    node_types: Record<string, number>;
    edge_types: Record<string, number>;
    top_connected: { id: string; label: string; degree: number }[];
  };
};

type Tab = "report" | "hypotheses" | "papers" | "graph";
type ExportFormat = "pdf" | "docx";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_MARA_API_KEY ?? "";

const authHeaders = () =>
  API_KEY ? { "X-MARA-API-Key": API_KEY } : {};

interface Props {
  report: string;
  hypotheses: Hypothesis[];
  papers: Paper[];
  graph_data: GraphData | null;
  onCitationClick?: (paper: Paper) => void;
}

/* ── Source badge component ────────────────────────────────────────────────── */
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

/* ── Main Component ───────────────────────────────────────────────────────── */
export default function ReportViewer({
  report,
  hypotheses,
  papers,
  graph_data,
  onCitationClick,
}: Props) {
  const [tab, setTab]       = useState<Tab>("report");
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  // Lazy import for KnowledgeGraphView
  const KnowledgeGraphView = require("./KnowledgeGraphView").default;

  const copyReport = useCallback(() => {
    navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [report]);

  const downloadReport = useCallback(() => {
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    // Create a clean filename from the first heading or first line
    const firstLine = report.split("\n").find((l) => l.trim().length > 0) || "research-report";
    const name = firstLine.replace(/^#+\s*/, "").replace(/[^a-zA-Z0-9 ]/g, "").trim().replace(/\s+/g, "-").slice(0, 60);
    a.download = `${name || "research-report"}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [report]);

  const exportReport = useCallback(async (format: ExportFormat) => {
    setExporting(format);
    try {
      const firstLine = report.split("\n").find((l) => l.trim().length > 0) || "research-report";
      const res = await fetch(`${API_URL}/export-report/${format}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({
          markdown: report,
          title: firstLine.replace(/^#+\s*/, ""),
        }),
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = firstLine.replace(/^#+\s*/, "").replace(/[^a-zA-Z0-9 ]/g, "").trim().replace(/\s+/g, "-").slice(0, 60);
      a.href = url;
      a.download = `${safeName || "research-report"}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(null);
    }
  }, [report]);

  const tabs: { key: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "report",    label: "Report",      icon: <FileText className="w-3.5 h-3.5" /> },
    { key: "hypotheses",label: "Hypotheses",   icon: <FlaskConical className="w-3.5 h-3.5" />, count: hypotheses.length },
    { key: "papers",    label: "Papers",       icon: <BookOpen className="w-3.5 h-3.5" />,     count: papers.length },
    { key: "graph",     label: "Graph",        icon: <Network className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="glass-card overflow-hidden animate-fade-in">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-4 pt-4 pb-2 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`tab flex items-center gap-1.5 whitespace-nowrap ${
              tab === t.key ? "tab-active" : ""
            }`}
          >
            {t.icon}
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className="bg-gray-800 text-gray-400 text-[10px] px-1.5 py-0.5 rounded-full">
                {t.count}
              </span>
            )}
          </button>
        ))}

        {/* Copy + Download buttons for report tab */}
        {tab === "report" && (
          <div className="ml-auto flex items-center gap-1">
            <button
              onClick={downloadReport}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1"
              title="Download as Markdown"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
            <button
              onClick={() => exportReport("pdf")}
              disabled={exporting !== null}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 disabled:opacity-50 transition-colors px-2 py-1"
              title="Export as PDF"
            >
              <Download className="w-3.5 h-3.5" />
              {exporting === "pdf" ? "PDF..." : "PDF"}
            </button>
            <button
              onClick={() => exportReport("docx")}
              disabled={exporting !== null}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 disabled:opacity-50 transition-colors px-2 py-1"
              title="Export as DOCX"
            >
              <Download className="w-3.5 h-3.5" />
              {exporting === "docx" ? "DOCX..." : "DOCX"}
            </button>
            <button
              onClick={copyReport}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </div>

      <div className="px-5 pb-5 max-h-[75vh] overflow-y-auto">
        {/* ── Report Tab ──────────────────────────────────────────────────── */}
        {tab === "report" && (
          <div className="report-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Make citation-like text clickable
                em: ({ children, ...props }) => <em {...props}>{children}</em>,
              }}
            >
              {report}
            </ReactMarkdown>
          </div>
        )}

        {/* ── Hypotheses Tab ──────────────────────────────────────────────── */}
        {tab === "hypotheses" && (
          <div className="space-y-3 mt-2">
            {hypotheses.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No hypotheses generated.</p>
            ) : (
              hypotheses.map((h, i) => (
                <div key={i} className="glass-card-hover p-4 animate-fade-in" style={{ animationDelay: `${i * 80}ms` }}>
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center text-pink-400 text-xs font-bold">
                      H{i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-200 leading-relaxed">
                        {h.hypothesis}
                      </p>
                      <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                        {h.justification}
                      </p>
                      {h.methodology_hint && (
                        <p className="text-xs text-indigo-400/70 mt-1 italic">
                          💡 {h.methodology_hint}
                        </p>
                      )}
                      <div className="mt-2 flex items-center gap-2">
                        <div className="progress-bar flex-1 max-w-[120px]">
                          <div
                            className="progress-bar-fill"
                            style={{ width: `${Math.round((h.confidence || 0) * 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {Math.round((h.confidence || 0) * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Papers Tab ──────────────────────────────────────────────────── */}
        {tab === "papers" && (
          <div className="space-y-3 mt-2">
            {papers.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No papers found.</p>
            ) : (
              papers.map((p, i) => (
                <div
                  key={i}
                  className="glass-card-hover p-4 cursor-pointer animate-fade-in"
                  style={{ animationDelay: `${i * 50}ms` }}
                  onClick={() => onCitationClick?.(p)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-gray-200 leading-snug line-clamp-2">
                        {p.title}
                      </h4>
                      <p className="text-[11px] text-gray-500 mt-1">
                        {p.authors.slice(0, 3).join(", ")}
                        {p.authors.length > 3 && " et al."}
                        {p.year ? ` · ${p.year}` : ""}
                      </p>
                      <p className="text-xs text-gray-400 mt-1.5 line-clamp-2 leading-relaxed">
                        {p.abstract}
                      </p>
                    </div>
                    {p.url && (
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="flex-shrink-0 text-gray-600 hover:text-indigo-400 transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-2.5">
                    <SourceBadge source={p.source} />
                    {p.citation_count > 0 && (
                      <span className="text-[10px] text-gray-500">
                        📊 {p.citation_count.toLocaleString()} citations
                      </span>
                    )}
                    {p.relevance_score > 0 && (
                      <span className="text-[10px] text-gray-600 font-mono ml-auto">
                        rel: {p.relevance_score.toFixed(3)}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Knowledge Graph Tab ─────────────────────────────────────────── */}
        {tab === "graph" && (
          <KnowledgeGraphView data={graph_data} />
        )}

      </div>
    </div>
  );
}
