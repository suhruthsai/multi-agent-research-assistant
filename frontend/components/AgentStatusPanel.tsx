"use client";
import { CheckCircle, Circle, Loader2 } from "lucide-react";

export type AgentStep = {
  node: string;
  status: string;
  paper_count?: number;
  confidence?: number;
  message?: { role: string; content: string };
};

const META: Record<string, { label: string; emoji: string; color: string }> = {
  search:        { label: "Search Agent",    emoji: "🔍", color: "text-blue-400" },
  critic:        { label: "Critic Agent",    emoji: "🧐", color: "text-yellow-400" },
  synthesis:     { label: "Synthesis Agent", emoji: "🧠", color: "text-purple-400" },
  loop_increment:{ label: "Reflector",       emoji: "🔁", color: "text-orange-400" },
  writer:        { label: "Writer Agent",    emoji: "✍️",  color: "text-green-400" },
  hypothesis:    { label: "Hypothesis Agent",emoji: "💡", color: "text-pink-400" },
};
const ORDER = ["search", "critic", "synthesis", "writer", "hypothesis"];

export default function AgentStatusPanel({ steps, isRunning }: { steps: AgentStep[]; isRunning: boolean }) {
  const completed = new Set(steps.map(s => s.node));
  const lastNode  = steps.at(-1)?.node;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-5">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent Pipeline</span>
        {isRunning && (
          <span className="flex items-center gap-1 text-xs text-indigo-400 bg-indigo-400/10 px-2 py-0.5 rounded-full">
            <Loader2 size={10} className="animate-spin" /> Running
          </span>
        )}
      </div>

      <div className="space-y-1">
        {ORDER.map((node, idx) => {
          const meta      = META[node];
          const isDone    = completed.has(node);
          const isActive  = isRunning && lastNode === node;
          const step      = steps.find(s => s.node === node);

          return (
            <div key={node} className="flex items-start gap-3">
              <div className="flex flex-col items-center">
                <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center transition-all
                  ${isDone   ? "border-emerald-500 bg-emerald-500/20" :
                    isActive ? "border-indigo-500 bg-indigo-500/20" :
                               "border-gray-700 bg-gray-800"}`}>
                  {isDone   ? <CheckCircle size={13} className="text-emerald-400" /> :
                   isActive ? <Loader2 size={13} className="text-indigo-400 animate-spin" /> :
                              <Circle size={13} className="text-gray-600" />}
                </div>
                {idx < ORDER.length - 1 && (
                  <div className={`w-0.5 h-5 mt-1 ${isDone ? "bg-emerald-500/30" : "bg-gray-800"}`} />
                )}
              </div>

              <div className="flex-1 pb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">{meta.emoji}</span>
                  <span className={`text-xs font-medium ${isDone ? meta.color : isActive ? "text-white" : "text-gray-600"}`}>
                    {meta.label}
                  </span>
                  {isActive && <span className="text-xs text-indigo-300 animate-pulse">processing…</span>}
                </div>
                {step && (
                  <div className="mt-1 text-xs text-gray-500 space-y-0.5">
                    {step.message?.content && <p className="text-gray-400">{step.message.content}</p>}
                    {(step.paper_count ?? 0) > 0 && <p>{step.paper_count} papers retrieved</p>}
                    {step.confidence != null && (
                      <div className="flex items-center gap-2 mt-1">
                        <span>Confidence</span>
                        <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${step.confidence >= 0.75 ? "bg-emerald-500" : step.confidence >= 0.5 ? "bg-yellow-500" : "bg-red-500"}`}
                            style={{ width: `${Math.round(step.confidence * 100)}%` }} />
                        </div>
                        <span>{Math.round(step.confidence * 100)}%</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {steps.length > 0 && (
        <div className="mt-3 border-t border-gray-800 pt-3">
          <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">Event log</p>
          <div className="space-y-1 max-h-28 overflow-y-auto">
            {steps.map((s, i) => (
              <div key={i} className="flex gap-2 text-xs text-gray-500">
                <span className="text-gray-700 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                <span className={META[s.node]?.color ?? "text-gray-400"}>[{META[s.node]?.label ?? s.node}]</span>
                <span>{s.message?.content ?? s.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}