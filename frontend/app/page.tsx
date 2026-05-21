"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { Search, Sparkles, X } from "lucide-react";
import AgentStatusPanel, { AgentStep } from "@/components/AgentStatusPanel";
import ReportViewer from "@/components/ReportViewer";

const WS_URL  = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/research";
const EXAMPLES = [
  "Transformer attention mechanisms in NLP",
  "CRISPR gene editing in cancer therapy",
  "Diffusion models for image generation",
  "Quantum computing error correction",
];

type FinalResult = {
  report: string; synthesis: string;
  hypotheses: any[]; papers: any[]; confidence_score: number;
};

export default function HomePage() {
  const [query,     setQuery]     = useState("");
  const [steps,     setSteps]     = useState<AgentStep[]>([]);
  const [result,    setResult]    = useState<FinalResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [elapsed,   setElapsed]   = useState(0);
  const wsRef      = useRef<WebSocket | null>(null);
  const timerRef   = useRef<NodeJS.Timeout | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ── Elapsed timer ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (isRunning) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isRunning]);

  const reset = () => { setSteps([]); setResult(null); setError(null); setElapsed(0); };

  const startResearch = useCallback(() => {
    if (!query.trim() || isRunning) return;
    reset();
    setIsRunning(true);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    // ── 5 minute timeout ────────────────────────────────────────────────────
    timeoutRef.current = setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
        setError("Request timed out after 5 minutes. Try a shorter/simpler query or click Research again.");
        setIsRunning(false);
      }
    }, 5 * 60 * 1000); // 5 minutes

    ws.onopen = () => ws.send(JSON.stringify({ query: query.trim() }));

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.error) {
        setError(data.error);
        setIsRunning(false);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        return;
      }
      if (data.node === "DONE") {
        setResult({
          report:           data.report ?? "",
          synthesis:        data.synthesis ?? "",
          hypotheses:       data.hypotheses ?? [],
          papers:           data.papers ?? [],
          confidence_score: data.confidence_score ?? 0,
        });
        setIsRunning(false);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        ws.close();
        return;
      }
      setSteps(prev => [...prev, data as AgentStep]);
    };

    ws.onerror  = () => {
      setError("Connection failed. Is the backend running on port 8000?");
      setIsRunning(false);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    ws.onclose  = () => setIsRunning(false);
  }, [query, isRunning]);

  const cancel = () => {
    wsRef.current?.close();
    setIsRunning(false);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  };

  const hasActivity = steps.length > 0 || result !== null;
  const mins = Math.floor(elapsed / 60);
  const secs = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800 bg-gray-900/70 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <Sparkles size={13} className="text-white" />
            </div>
            <span className="font-semibold text-white text-sm">MARA</span>
            <span className="text-xs text-gray-600 hidden sm:block">Multi-Agent Research Assistant</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            {isRunning && (
              <span className="text-indigo-400 font-mono">
                {mins}:{secs}
              </span>
            )}
            <div className={`w-1.5 h-1.5 rounded-full ${isRunning ? "bg-green-400 animate-pulse" : "bg-gray-700"}`} />
            {isRunning ? "Agents running" : "Ready"}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        {!hasActivity && (
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-indigo-500/10 text-indigo-400 text-xs px-3 py-1 rounded-full border border-indigo-500/20 mb-4">
              <Sparkles size={11} /> 5 specialist AI agents
            </div>
            <h1 className="text-4xl font-bold text-white mb-3">
              Research anything,<br />
              <span className="text-indigo-400">deeply and automatically.</span>
            </h1>
            <p className="text-gray-400 text-sm max-w-md mx-auto">
              Searches 200M+ papers across 4 sources, critiques evidence, synthesises findings,
              and generates a full cited report with novel hypotheses.
            </p>
          </div>
        )}

        <div className={`flex items-center gap-3 bg-gray-900 border rounded-2xl px-4 py-3 mb-3 transition-all
          ${isRunning ? "border-indigo-500 shadow-[0_0_0_3px_rgba(99,102,241,0.12)]" : "border-gray-700 focus-within:border-indigo-600"}`}>
          <Search size={16} className="text-gray-500 shrink-0" />
          <input
            value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && startResearch()}
            placeholder="Ask a research question…" disabled={isRunning}
            className="flex-1 bg-transparent text-white placeholder-gray-600 text-sm focus:outline-none disabled:opacity-50"
          />
          {query && !isRunning && (
            <button onClick={() => setQuery("")} className="text-gray-600 hover:text-gray-300">
              <X size={15} />
            </button>
          )}
          {isRunning
            ? <button onClick={cancel}
                className="shrink-0 px-3 py-1.5 bg-red-600/20 text-red-400 text-xs rounded-xl border border-red-600/30 hover:bg-red-600/30">
                Stop
              </button>
            : <button onClick={startResearch} disabled={!query.trim()}
                className="shrink-0 flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium rounded-xl transition-all">
                <Sparkles size={12} /> Research
              </button>
          }
        </div>

        {!hasActivity && (
          <div className="flex flex-wrap gap-2 justify-center mb-10">
            {EXAMPLES.map(q => (
              <button key={q} onClick={() => setQuery(q)}
                className="text-xs text-gray-400 hover:text-white bg-gray-800/60 hover:bg-gray-800 border border-gray-700/50 px-3 py-1.5 rounded-full transition-all">
                {q}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="mb-5 flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-400 text-xs px-4 py-3 rounded-xl">
            <X size={14} className="shrink-0" /> {error}
          </div>
        )}

        {hasActivity && (
          <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">
            <div className="lg:sticky lg:top-20 lg:self-start space-y-4">
              <AgentStatusPanel steps={steps} isRunning={isRunning} />
              {result && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Papers",     value: result.papers.length },
                    { label: "Hypotheses", value: result.hypotheses.length },
                    { label: "Confidence", value: `${Math.round(result.confidence_score * 100)}%` },
                  ].map(s => (
                    <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
                      <p className="text-xl font-bold text-white">{s.value}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              {result
                ? <ReportViewer {...result} />
                : (
                  <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
                      <span className="text-xs text-gray-400">
                        Agents working… this takes 2–4 minutes for deep research
                      </span>
                    </div>
                    <div className="space-y-3 animate-pulse">
                      <div className="h-5 bg-gray-800 rounded w-2/3" />
                      <div className="h-3 bg-gray-800 rounded w-full" />
                      <div className="h-3 bg-gray-800 rounded w-5/6" />
                      <div className="h-3 bg-gray-800 rounded w-4/6" />
                      <div className="h-5 bg-gray-800 rounded w-1/2 mt-6" />
                      <div className="h-3 bg-gray-800 rounded w-full" />
                      <div className="h-3 bg-gray-800 rounded w-3/4" />
                    </div>
                  </div>
                )
              }
            </div>
          </div>
        )}
      </main>
    </div>
  );
}