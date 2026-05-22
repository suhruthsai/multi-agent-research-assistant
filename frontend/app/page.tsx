"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { Search, Sparkles, X, Zap, Brain, BookOpen, Network, Shield, History } from "lucide-react";
import AgentStatusPanel, { AgentStep } from "@/components/AgentStatusPanel";
import ReportViewer, { Paper, Hypothesis, FactCheck, GraphData } from "@/components/ReportViewer";
import CitationSidebar from "@/components/CitationSidebar";
import HistorySidebar from "@/components/HistorySidebar";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/research";

const EXAMPLES = [
  "Transformer attention mechanisms in NLP",
  "CRISPR gene editing in cancer therapy",
  "Diffusion models for image generation",
  "Quantum computing error correction",
  "Large language model alignment techniques",
  "Graph neural networks for drug discovery",
];

const FEATURES = [
  { icon: <Zap className="w-5 h-5" />, title: "Hybrid RAG", desc: "BM25 + Semantic + Re-ranking" },
  { icon: <Brain className="w-5 h-5" />, title: "7 AI Agents", desc: "Specialized research pipeline" },
  { icon: <BookOpen className="w-5 h-5" />, title: "Full-Text PDFs", desc: "Deep paper analysis" },
  { icon: <Network className="w-5 h-5" />, title: "Knowledge Graph", desc: "Paper relationship mapping" },
  { icon: <Shield className="w-5 h-5" />, title: "Fact Checker", desc: "Claim verification" },
];

type FinalResult = {
  report: string;
  synthesis: string;
  research_plan: string;
  hypotheses: Hypothesis[];
  papers: Paper[];
  fact_check_results: FactCheck[];
  graph_data: GraphData | null;
  confidence_score: number;
  pdf_processed_count: number;
  topics: string[];
};

export default function HomePage() {
  const [query, setQuery]         = useState("");
  const [steps, setSteps]         = useState<AgentStep[]>([]);
  const [result, setResult]       = useState<FinalResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [elapsed, setElapsed]     = useState(0);
  const [sidebarPaper, setSidebarPaper] = useState<Paper | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const wsRef      = useRef<WebSocket | null>(null);
  const timerRef   = useRef<NodeJS.Timeout | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Elapsed timer
  useEffect(() => {
    if (isRunning) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  const reset = () => {
    setSteps([]);
    setResult(null);
    setError(null);
    setElapsed(0);
  };

  const startResearch = useCallback(() => {
    if (!query.trim() || isRunning) return;
    reset();
    setIsRunning(true);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    // 8 minute timeout (longer due to PDF processing)
    timeoutRef.current = setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
        setError(
          "Request timed out after 8 minutes. Try a shorter/simpler query or click Research again."
        );
        setIsRunning(false);
      }
    }, 8 * 60 * 1000);

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
          report:             data.report ?? "",
          synthesis:          data.synthesis ?? "",
          research_plan:      data.research_plan ?? "",
          hypotheses:         data.hypotheses ?? [],
          papers:             data.papers ?? [],
          fact_check_results: data.fact_check_results ?? [],
          graph_data:         data.graph_data ?? null,
          confidence_score:   data.confidence_score ?? 0,
          pdf_processed_count: data.pdf_processed_count ?? 0,
          topics:             data.topics ?? [],
        });
        setIsRunning(false);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        ws.close();
        return;
      }

      setSteps((prev) => [...prev, data as AgentStep]);
    };

    ws.onerror = () => {
      setError("Connection failed. Is the backend running on port 8000?");
      setIsRunning(false);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    ws.onclose = () => setIsRunning(false);
  }, [query, isRunning]);

  const cancel = () => {
    wsRef.current?.close();
    setIsRunning(false);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      startResearch();
    }
  };

  // Load a report from history
  const loadHistoryReport = useCallback((data: any) => {
    reset();
    setQuery(data.query || "");
    setResult({
      report:             data.report ?? "",
      synthesis:          data.synthesis ?? "",
      research_plan:      data.research_plan ?? "",
      hypotheses:         data.hypotheses ?? [],
      papers:             data.papers ?? [],
      fact_check_results: data.fact_check_results ?? [],
      graph_data:         data.graph_data ?? null,
      confidence_score:   data.confidence_score ?? 0,
      pdf_processed_count: data.pdf_processed_count ?? 0,
      topics:             data.topics ?? [],
    });
  }, []);

  const hasActivity = steps.length > 0 || result !== null;
  const mins = Math.floor(elapsed / 60);
  const secs = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="min-h-screen bg-[#06080f]">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-gray-800/50 bg-[#06080f]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight">
                <span className="gradient-text">MARA</span>
              </h1>
              <p className="text-[10px] text-gray-600 -mt-0.5">Multi-Agent Research Assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setHistoryOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-500
                         hover:text-gray-300 hover:bg-gray-800/50 transition-all duration-200"
            >
              <History className="w-3.5 h-3.5" />
              History
            </button>
            {isRunning && (
              <span className="flex items-center gap-2 text-xs text-indigo-400">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                </span>
                Processing
              </span>
            )}
            <span className="text-xs text-gray-600 font-mono tabular-nums">
              {mins}:{secs}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* ── Hero (no activity) ───────────────────────────────────────────── */}
        {!hasActivity && (
          <div className="text-center pt-16 pb-10 animate-fade-in">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-6">
              <Sparkles className="w-3 h-3" />
              7 Specialist AI Agents · Hybrid RAG · Knowledge Graph
            </div>
            <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4">
              <span className="gradient-text">Research Anything</span>
              <br />
              <span className="text-gray-300">with AI Agents</span>
            </h2>
            <p className="text-gray-500 max-w-xl mx-auto text-sm leading-relaxed">
              MARA searches 250M+ academic papers across Semantic Scholar, arXiv,
              OpenAlex &amp; CrossRef, then synthesizes findings with a team of
              specialized AI agents.
            </p>

            {/* Feature chips */}
            <div className="flex flex-wrap justify-center gap-3 mt-8">
              {FEATURES.map((f, i) => (
                <div
                  key={i}
                  className="glass-card px-4 py-2.5 flex items-center gap-2.5 animate-fade-in"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <span className="text-indigo-400">{f.icon}</span>
                  <div className="text-left">
                    <p className="text-xs font-semibold text-gray-300">{f.title}</p>
                    <p className="text-[10px] text-gray-600">{f.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Search Bar ───────────────────────────────────────────────────── */}
        <div className={`${hasActivity ? "mb-6" : "mt-8 mb-6"} max-w-3xl mx-auto`}>
          <div className="glass-card p-2 flex items-center gap-2">
            <div className="flex items-center pl-3 text-gray-500">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter a research topic..."
              className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none py-2.5"
              disabled={isRunning}
            />
            {query && !isRunning && (
              <button
                onClick={() => setQuery("")}
                className="p-1.5 text-gray-600 hover:text-gray-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            {isRunning ? (
              <button onClick={cancel} className="btn-danger text-white text-xs">
                Stop
              </button>
            ) : (
              <button
                onClick={startResearch}
                disabled={!query.trim()}
                className="btn-primary text-white text-xs"
              >
                Research
              </button>
            )}
          </div>
        </div>

        {/* ── Example Queries ──────────────────────────────────────────────── */}
        {!hasActivity && (
          <div className="max-w-3xl mx-auto mb-12">
            <p className="text-[11px] text-gray-600 mb-2 text-center">Try an example:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(ex)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-gray-900/50 border border-gray-800/50 
                             text-gray-500 hover:text-gray-300 hover:border-gray-700 transition-all duration-200"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Error ────────────────────────────────────────────────────────── */}
        {error && (
          <div className="max-w-3xl mx-auto mb-6 animate-fade-in">
            <div className="glass-card border-red-500/30 bg-red-500/5 p-4 flex items-start gap-3">
              <span className="text-red-400 text-lg">⚠️</span>
              <div>
                <p className="text-sm text-red-300 font-medium">Error</p>
                <p className="text-xs text-red-400/70 mt-1">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="ml-auto text-gray-600 hover:text-gray-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ── Results Grid ─────────────────────────────────────────────────── */}
        {hasActivity && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5 animate-fade-in">
            {/* Left sidebar */}
            <div className="space-y-4">
              <AgentStatusPanel steps={steps} isRunning={isRunning} />

              {/* Stats cards */}
              {result && (
                <div className="grid grid-cols-2 gap-2">
                  <div className="glass-card p-3 text-center">
                    <p className="text-lg font-bold text-indigo-400">
                      {result.papers.length}
                    </p>
                    <p className="text-[10px] text-gray-500">Papers</p>
                  </div>
                  <div className="glass-card p-3 text-center">
                    <p className="text-lg font-bold text-pink-400">
                      {result.hypotheses.length}
                    </p>
                    <p className="text-[10px] text-gray-500">Hypotheses</p>
                  </div>
                  <div className="glass-card p-3 text-center">
                    <p className="text-lg font-bold text-emerald-400">
                      {result.pdf_processed_count}
                    </p>
                    <p className="text-[10px] text-gray-500">PDFs Parsed</p>
                  </div>
                  <div className="glass-card p-3 text-center">
                    <p className="text-lg font-bold text-cyan-400">
                      {Math.round(result.confidence_score * 100)}%
                    </p>
                    <p className="text-[10px] text-gray-500">Confidence</p>
                  </div>
                </div>
              )}

              {/* Topics */}
              {result && result.topics.length > 0 && (
                <div className="glass-card p-3">
                  <p className="text-[11px] text-gray-500 mb-2">Topics</p>
                  <div className="flex flex-wrap gap-1">
                    {result.topics.map((t, i) => (
                      <span
                        key={i}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/20"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right content */}
            <div>
              {result ? (
                <ReportViewer
                  report={result.report}
                  synthesis={result.synthesis}
                  research_plan={result.research_plan}
                  hypotheses={result.hypotheses}
                  papers={result.papers}
                  fact_check_results={result.fact_check_results}
                  graph_data={result.graph_data}
                  confidence_score={result.confidence_score}
                  onCitationClick={(paper) => setSidebarPaper(paper)}
                />
              ) : (
                /* Skeleton loading */
                <div className="glass-card p-6 space-y-4">
                  <div className="flex gap-2 mb-4">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div key={i} className="skeleton h-8 w-20 rounded-xl" />
                    ))}
                  </div>
                  <div className="skeleton h-6 w-3/4 rounded" />
                  <div className="skeleton h-4 w-full rounded" />
                  <div className="skeleton h-4 w-full rounded" />
                  <div className="skeleton h-4 w-5/6 rounded" />
                  <div className="skeleton h-4 w-full rounded" />
                  <div className="skeleton h-4 w-2/3 rounded" />
                  <div className="skeleton h-6 w-1/2 rounded mt-4" />
                  <div className="skeleton h-4 w-full rounded" />
                  <div className="skeleton h-4 w-full rounded" />
                  <div className="skeleton h-4 w-4/5 rounded" />
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── Citation Sidebar ───────────────────────────────────────────────── */}
      <CitationSidebar
        paper={sidebarPaper}
        onClose={() => setSidebarPaper(null)}
      />
      <HistorySidebar
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onLoadReport={loadHistoryReport}
      />
    </div>
  );
}