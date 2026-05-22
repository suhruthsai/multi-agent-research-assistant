"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

type FactCheck = {
  claim: string;
  status: string;
  evidence: string;
  source_paper: string;
};

interface FactCheckPanelProps {
  results: FactCheck[];
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; bg: string; label: string }> = {
  verified:     { icon: "✅", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", label: "Verified" },
  unverified:   { icon: "⚠️", color: "text-amber-400",   bg: "bg-amber-500/10 border-amber-500/20",   label: "Unverified" },
  contradicted: { icon: "❌", color: "text-red-400",     bg: "bg-red-500/10 border-red-500/20",       label: "Contradicted" },
};

export default function FactCheckPanel({ results }: FactCheckPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!results || results.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 text-sm">No fact-check results available.</p>
        <p className="text-gray-700 text-xs mt-1">
          The fact-checker agent verifies claims in the report against source papers.
        </p>
      </div>
    );
  }

  const verified = results.filter((r) => r.status === "verified").length;
  const total    = results.length;
  const pct      = Math.round((verified / total) * 100);

  return (
    <div className="space-y-4 mt-2">
      {/* Summary bar */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg">🛡️</span>
            <span className="text-sm font-semibold text-gray-300">Verification Summary</span>
          </div>
          <span className="text-sm font-mono text-gray-400">
            <span className="text-emerald-400">{verified}</span>/{total} verified
          </span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-bar-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex justify-between mt-1.5 text-[10px] text-gray-600">
          <span>{pct}% verified</span>
          <span>
            {results.filter((r) => r.status === "contradicted").length} contradicted
          </span>
        </div>
      </div>

      {/* Fact check cards */}
      {results.map((fc, i) => {
        const config    = STATUS_CONFIG[fc.status] || STATUS_CONFIG.unverified;
        const isExpanded = expanded === i;

        return (
          <div
            key={i}
            className={`border rounded-xl transition-all duration-200 cursor-pointer ${config.bg}`}
            onClick={() => setExpanded(isExpanded ? null : i)}
          >
            <div className="p-3.5 flex items-start gap-3">
              <span className="text-sm mt-0.5 flex-shrink-0">{config.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-300 leading-relaxed line-clamp-2">
                  {fc.claim}
                </p>
                <span className={`text-[10px] font-medium uppercase tracking-wider ${config.color}`}>
                  {config.label}
                </span>
              </div>
              <span className="flex-shrink-0 text-gray-600 mt-0.5">
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </span>
            </div>

            {isExpanded && (
              <div className="px-3.5 pb-3.5 pt-0 border-t border-gray-800/30 mt-0 animate-fade-in">
                <div className="pt-3 space-y-2">
                  <div>
                    <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">
                      Evidence
                    </p>
                    <p className="text-xs text-gray-400 leading-relaxed">
                      {fc.evidence || "No evidence provided."}
                    </p>
                  </div>
                  {fc.source_paper && fc.source_paper !== "None" && (
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">
                        Source Paper
                      </p>
                      <p className="text-xs text-indigo-400">{fc.source_paper}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
