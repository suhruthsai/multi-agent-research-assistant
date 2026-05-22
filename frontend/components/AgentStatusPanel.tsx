"use client";
import { CheckCircle, Circle, Loader2 } from "lucide-react";

export type AgentStep = {
  node: string;
  status: string;
  paper_count?: number;
  confidence?: number;
  pdf_processed_count?: number;
  chunk_count?: number;
  topics?: string[];
  research_plan?: string;
  message?: { role: string; content: string };
};

const META: Record<string, { label: string; emoji: string; color: string; desc: string }> = {
  planner:        { label: "Planner Agent",      emoji: "📋", color: "text-sky-400",    desc: "Creating research plan" },
  search:         { label: "Search Agent",       emoji: "🔍", color: "text-blue-400",   desc: "Hybrid search + PDF processing" },
  critic:         { label: "Critic Agent",       emoji: "🧐", color: "text-yellow-400", desc: "Evaluating paper quality" },
  synthesis:      { label: "Synthesis Agent",    emoji: "🧠", color: "text-purple-400", desc: "Cross-paper analysis" },
  loop_increment: { label: "Reflector",          emoji: "🔁", color: "text-orange-400", desc: "Re-evaluating confidence" },
  writer:         { label: "Writer Agent",       emoji: "✍️",  color: "text-green-400",  desc: "Generating research report" },
  fact_checker:   { label: "Fact-Checker Agent", emoji: "✅", color: "text-emerald-400", desc: "Verifying claims" },
  hypothesis:     { label: "Hypothesis Agent",   emoji: "💡", color: "text-pink-400",   desc: "Generating novel hypotheses" },
};

const ORDER = ["planner", "search", "critic", "synthesis", "writer", "fact_checker", "hypothesis"];

interface Props {
  steps: AgentStep[];
  isRunning: boolean;
}

export default function AgentStatusPanel({ steps, isRunning }: Props) {
  // Track which agents have completed
  const completed = new Set(steps.map((s) => s.node));
  const lastStep  = steps[steps.length - 1];
  const activeNode = isRunning ? lastStep?.node : null;

  // Get the last message for a node
  const lastMsgForNode = (node: string): string => {
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].node === node && steps[i].message?.content) {
        return steps[i].message!.content;
      }
    }
    return "";
  };

  // Get latest confidence from steps
  const latestConfidence = (() => {
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].confidence != null) return steps[i].confidence!;
    }
    return 0;
  })();

  return (
    <div className="glass-card p-4 space-y-1">
      <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <span className="text-indigo-400">⚡</span>
        Agent Pipeline
        {isRunning && (
          <span className="ml-auto flex items-center gap-1 text-xs text-indigo-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            Running
          </span>
        )}
      </h3>

      {ORDER.map((node, i) => {
        const meta     = META[node];
        const isDone   = completed.has(node);
        const isActive = activeNode === node;
        const msg      = lastMsgForNode(node);

        return (
          <div key={node} className="animate-fade-in" style={{ animationDelay: `${i * 50}ms` }}>
            {/* Connecting line */}
            {i > 0 && (
              <div className="flex justify-start pl-[15px]">
                <div
                  className={`w-px h-3 transition-colors duration-300 ${
                    isDone || isActive ? "bg-indigo-500/50" : "bg-gray-800"
                  }`}
                />
              </div>
            )}

            {/* Agent row */}
            <div
              className={`flex items-start gap-3 px-2 py-1.5 rounded-lg transition-all duration-300 ${
                isActive
                  ? "bg-indigo-500/10 border border-indigo-500/20"
                  : isDone
                  ? "opacity-80"
                  : "opacity-40"
              }`}
            >
              {/* Status icon */}
              <div className="mt-0.5 flex-shrink-0">
                {isDone && !isActive ? (
                  <CheckCircle className="w-[18px] h-[18px] text-emerald-400" />
                ) : isActive ? (
                  <Loader2 className="w-[18px] h-[18px] text-indigo-400 animate-spin" />
                ) : (
                  <Circle className="w-[18px] h-[18px] text-gray-700" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{meta.emoji}</span>
                  <span className={`text-xs font-semibold ${meta.color}`}>
                    {meta.label}
                  </span>
                </div>
                {(isActive || isDone) && msg && (
                  <p className="text-[11px] text-gray-500 mt-0.5 truncate">
                    {msg}
                  </p>
                )}
                {isActive && !isDone && (
                  <p className="text-[11px] text-gray-600 mt-0.5 italic">
                    {meta.desc}...
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {/* Confidence bar */}
      {latestConfidence > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800/50">
          <div className="flex items-center justify-between text-[11px] text-gray-400 mb-1">
            <span>Confidence</span>
            <span className="font-mono">{Math.round(latestConfidence * 100)}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round(latestConfidence * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Event log */}
      {steps.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800/50">
          <details className="group">
            <summary className="text-[11px] text-gray-500 cursor-pointer hover:text-gray-400 transition-colors">
              Event log ({steps.length})
            </summary>
            <div className="mt-2 max-h-32 overflow-y-auto space-y-1">
              {steps.map((s, i) => (
                <div key={i} className="text-[10px] text-gray-600 flex gap-2">
                  <span className="text-gray-700 flex-shrink-0">
                    {META[s.node]?.emoji || "•"}
                  </span>
                  <span className="truncate">
                    {s.message?.content || s.status}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}