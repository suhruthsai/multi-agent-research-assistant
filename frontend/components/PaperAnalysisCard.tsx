"use client";
import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Lightbulb,
  FileText,
  FlaskConical,
  BookOpen,
} from "lucide-react";

export type PaperAnalysis = {
  title: string;
  summary: string;
  advantages: string[];
  disadvantages: string[];
  key_findings: string[];
  methodology: string;
  source_type: "pdf" | "text";
  filename: string;
};

interface Props {
  analysis: PaperAnalysis;
  index: number;
}

export default function PaperAnalysisCard({ analysis, index }: Props) {
  const [expanded, setExpanded] = useState(true);

  const isPdf = analysis.source_type === "pdf";

  // Safe normalized fields to prevent crash from malformed LLM responses
  const summaryParagraphs = (() => {
    const s: unknown = analysis.summary;
    if (!s) return ["No summary generated."];
    if (Array.isArray(s)) {
      return (s as unknown[]).filter(Boolean).map(p => String(p).trim());
    }
    if (typeof s === "string") {
      return s.split("\n\n").filter(Boolean).map(p => p.trim());
    }
    return [String(s).trim()];
  })();

  const safeAdvantages = Array.isArray(analysis.advantages)
    ? analysis.advantages
    : typeof analysis.advantages === "string" && (analysis.advantages as string).trim()
      ? [analysis.advantages]
      : [];

  const safeDisadvantages = Array.isArray(analysis.disadvantages)
    ? analysis.disadvantages
    : typeof analysis.disadvantages === "string" && (analysis.disadvantages as string).trim()
      ? [analysis.disadvantages]
      : [];

  const safeKeyFindings = Array.isArray(analysis.key_findings)
    ? analysis.key_findings
    : typeof analysis.key_findings === "string" && (analysis.key_findings as string).trim()
      ? [analysis.key_findings]
      : [];

  const safeMethodology = typeof analysis.methodology === "string" ? analysis.methodology : "";

  return (
    <div
      className="glass-card overflow-hidden animate-fade-in"
      style={{ animationDelay: `${index * 120}ms` }}
    >
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-start gap-4 p-5 text-left hover:bg-white/[0.02] transition-colors"
      >
        {/* Paper number badge */}
        <span className="flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 text-sm font-bold">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {/* Source badge */}
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                isPdf
                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/25"
                  : "bg-blue-500/15 text-blue-400 border border-blue-500/25"
              }`}
            >
              {isPdf ? <FileText className="w-2.5 h-2.5" /> : <BookOpen className="w-2.5 h-2.5" />}
              {isPdf ? "PDF" : "Text"}
            </span>
            <span className="text-[10px] text-gray-600 truncate max-w-[200px]">
              {analysis.filename !== "manual_input" ? analysis.filename : "Pasted Input"}
            </span>
          </div>

          <h3 className="text-sm font-semibold text-gray-100 leading-snug line-clamp-2">
            {analysis.title || "Untitled Paper"}
          </h3>

          {safeMethodology && (
            <p className="text-[11px] text-indigo-400/80 mt-1 line-clamp-1">
              📐 {safeMethodology}
            </p>
          )}
        </div>

        {/* Stats strip */}
        <div className="flex-shrink-0 flex items-center gap-3 mr-1">
          <div className="text-center">
            <p className="text-xs font-bold text-emerald-400">{safeAdvantages.length}</p>
            <p className="text-[9px] text-gray-600">Pros</p>
          </div>
          <div className="text-center">
            <p className="text-xs font-bold text-red-400">{safeDisadvantages.length}</p>
            <p className="text-[9px] text-gray-600">Cons</p>
          </div>
          <div className="text-gray-600 ml-1">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </button>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      {expanded && (
        <div className="px-5 pb-5 space-y-5 border-t border-gray-800/40 pt-4">
          {/* Summary */}
          <div>
            <h4 className="flex items-center gap-1.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
              <FlaskConical className="w-3.5 h-3.5 text-indigo-400" />
              Summary
            </h4>
            <div className="text-sm text-gray-300 leading-relaxed space-y-2">
              {summaryParagraphs.map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          </div>

          {/* Key Findings */}
          {safeKeyFindings.length > 0 && (
            <div>
              <h4 className="flex items-center gap-1.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                Key Findings
              </h4>
              <ul className="space-y-1.5">
                {safeKeyFindings.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-400 text-[10px] font-bold flex items-center justify-center mt-0.5">
                      {i + 1}
                    </span>
                    <span className="leading-relaxed">{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Advantages & Disadvantages side-by-side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Advantages */}
            <div className="bg-emerald-500/5 border border-emerald-500/15 rounded-xl p-4">
              <h4 className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400 uppercase tracking-wider mb-3">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Advantages
              </h4>
              {safeAdvantages.length === 0 ? (
                <p className="text-xs text-gray-600 italic">None explicitly stated in the paper.</p>
              ) : (
                <ul className="space-y-2">
                  {safeAdvantages.map((adv, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-300 leading-relaxed">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/70 flex-shrink-0 mt-0.5" />
                      <span>{adv}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Disadvantages */}
            <div className="bg-red-500/5 border border-red-500/15 rounded-xl p-4">
              <h4 className="flex items-center gap-1.5 text-[11px] font-semibold text-red-400 uppercase tracking-wider mb-3">
                <XCircle className="w-3.5 h-3.5" />
                Disadvantages
              </h4>
              {safeDisadvantages.length === 0 ? (
                <p className="text-xs text-gray-600 italic">No explicit limitations mentioned.</p>
              ) : (
                <ul className="space-y-2">
                  {safeDisadvantages.map((dis, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-300 leading-relaxed">
                      <XCircle className="w-3.5 h-3.5 text-red-500/70 flex-shrink-0 mt-0.5" />
                      <span>{dis}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
