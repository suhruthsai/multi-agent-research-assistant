"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import {
  Upload,
  Plus,
  X,
  FileText,
  Loader2,
  Trash2,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react";
import PaperAnalysisCard, { PaperAnalysis } from "./PaperAnalysisCard";
import ComparativeAnalysis from "./ComparativeAnalysis";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL?.replace("/ws/research", "") ?? "ws://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_MARA_API_KEY ?? "";

// ── Types ─────────────────────────────────────────────────────────────────────
type PaperInput =
  | { type: "pdf"; file: File; title: string }
  | { type: "text"; title: string; text: string };

type AnalysisResult = {
  paper_analyses: PaperAnalysis[];
  comparative_analysis: string;
  paper_count: number;
};

type Status = "idle" | "running" | "done" | "error";

// ── Helper: read File as base64 ───────────────────────────────────────────────
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip data URL prefix: "data:...;base64,"
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// ── Empty text-input form ─────────────────────────────────────────────────────
const EMPTY_TEXT: { title: string; text: string } = { title: "", text: "" };

// ═════════════════════════════════════════════════════════════════════════════
export default function PaperAnalyzer() {
  const [papers, setPapers] = useState<PaperInput[]>([]);
  const [textDraft, setTextDraft] = useState({ ...EMPTY_TEXT });
  const [showTextForm, setShowTextForm] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Drag & Drop ─────────────────────────────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => f.type === "application/pdf"
    );
    addPdfFiles(files);
  }, []);

  const addPdfFiles = (files: File[]) => {
    const newPapers: PaperInput[] = files.map((f) => ({
      type: "pdf",
      file: f,
      title: f.name.replace(/\.pdf$/i, "").replace(/[_-]/g, " "),
    }));
    setPapers((prev) => [...prev, ...newPapers]);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter(
      (f) => f.type === "application/pdf"
    );
    addPdfFiles(files);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removePaper = (idx: number) =>
    setPapers((prev) => prev.filter((_, i) => i !== idx));

  const updatePaperTitle = (idx: number, title: string) =>
    setPapers((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, title } : p))
    );

  // ── Add pasted text ──────────────────────────────────────────────────────────
  const addTextPaper = () => {
    if (!textDraft.text.trim()) return;
    setPapers((prev) => [
      ...prev,
      {
        type: "text",
        title: textDraft.title.trim() || "Pasted Paper",
        text: textDraft.text.trim(),
      },
    ]);
    setTextDraft({ ...EMPTY_TEXT });
    setShowTextForm(false);
  };

  // ── Run analysis via WebSocket ────────────────────────────────────────────────
  const runAnalysis = useCallback(async () => {
    if (papers.length === 0 || status === "running") return;
    setStatus("running");
    setError(null);
    setResult(null);
    setStatusMsg("Preparing papers…");

    // Build payload: convert PDFs to base64 on the client
    const payload: any[] = [];
    for (const p of papers) {
      if (p.type === "pdf") {
        try {
          setStatusMsg(`Reading ${p.file.name}…`);
          const b64 = await fileToBase64(p.file);
          payload.push({
            source_type: "pdf",
            title: p.title,
            filename: p.file.name,
            pdf_b64: b64,
          });
        } catch (err) {
          console.error("Failed to read file", p.file.name, err);
        }
      } else {
        payload.push({
          source_type: "text",
          title: p.title,
          filename: "manual_input",
          full_text: p.text,
        });
      }
    }

    if (payload.length === 0) {
      setError("No valid papers could be prepared.");
      setStatus("error");
      return;
    }

    setStatusMsg("Connecting to analysis pipeline…");

    const ws = new WebSocket(`${WS_URL}/ws/analyze-papers`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatusMsg("Analyzing papers… this may take a minute.");
      ws.send(JSON.stringify({ papers: payload, api_key: API_KEY || undefined }));
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.error) {
        setError(data.error);
        setStatus("error");
        ws.close();
        return;
      }

      if (data.node === "paper_analyzer") {
        setStatusMsg(
          `✅ Paper analysis complete — ${data.paper_analyses?.length ?? 0} papers analyzed`
        );
      }

      if (data.node === "comparative_analyzer") {
        setStatusMsg("✅ Comparative analysis generated");
      }

      if (data.node === "DONE") {
        setResult({
          paper_analyses: data.paper_analyses ?? [],
          comparative_analysis: data.comparative_analysis ?? "",
          paper_count: data.paper_count ?? 0,
        });
        setStatus("done");
        setStatusMsg("");
        ws.close();
      }
    };

    ws.onerror = () => {
      setError("Connection failed. Is the backend running on port 8000?");
      setStatus("error");
    };

    ws.onclose = () => {
      // status is managed by onmessage/onerror — no update needed here
    };
  }, [papers, status]);

  const cancel = () => {
    wsRef.current?.close();
    setStatus("idle");
    setStatusMsg("");
  };

  const reset = () => {
    cancel();
    setResult(null);
    setError(null);
    setPapers([]);
  };

  const isRunning = status === "running";
  const isDone = status === "done";

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 animate-fade-in">
      {/* ── Upload Panel ──────────────────────────────────────────────────── */}
      {!isDone && (
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-indigo-400" />
                Add Your Research Papers
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Upload PDFs or paste text / abstracts
              </p>
            </div>
            {papers.length > 0 && !isRunning && (
              <button
                onClick={reset}
                className="text-xs text-gray-600 hover:text-gray-400 flex items-center gap-1"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear all
              </button>
            )}
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !isRunning && fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 ${
              dragOver
                ? "border-indigo-500/70 bg-indigo-500/10"
                : "border-gray-700/50 hover:border-indigo-500/40 hover:bg-indigo-500/5"
            } ${isRunning ? "pointer-events-none opacity-50" : ""}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileInput}
              disabled={isRunning}
            />
            <Upload className="w-8 h-8 text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-400 font-medium">
              Drop PDF files here or <span className="text-indigo-400">click to browse</span>
            </p>
            <p className="text-xs text-gray-600 mt-1">Multiple PDFs supported</p>
          </div>

          {/* Added papers list */}
          {papers.length > 0 && (
            <div className="space-y-2">
              {papers.map((p, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 bg-gray-900/40 rounded-xl border border-gray-800/40"
                >
                  <span
                    className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                      p.type === "pdf"
                        ? "bg-orange-500/15 text-orange-400 border border-orange-500/20"
                        : "bg-blue-500/15 text-blue-400 border border-blue-500/20"
                    }`}
                  >
                    {p.type === "pdf" ? (
                      <span className="flex items-center gap-1">
                        <FileText className="w-2.5 h-2.5" /> PDF
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <BookOpen className="w-2.5 h-2.5" /> Text
                      </span>
                    )}
                  </span>

                  <input
                    type="text"
                    value={p.title}
                    onChange={(e) => updatePaperTitle(i, e.target.value)}
                    disabled={isRunning}
                    className="flex-1 bg-transparent text-xs text-gray-200 outline-none min-w-0 placeholder-gray-600"
                    placeholder="Paper title…"
                  />

                  {p.type === "pdf" && (
                    <span className="text-[10px] text-gray-600 whitespace-nowrap">
                      {(p.file.size / 1024).toFixed(0)} KB
                    </span>
                  )}

                  {!isRunning && (
                    <button
                      onClick={() => removePaper(i)}
                      className="text-gray-700 hover:text-red-400 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Add text / abstract */}
          {!isRunning && (
            <button
              onClick={() => setShowTextForm((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-indigo-400 transition-colors"
            >
              {showTextForm ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <Plus className="w-3.5 h-3.5" />
              )}
              {showTextForm ? "Cancel text input" : "Paste text / abstract instead"}
            </button>
          )}

          {showTextForm && !isRunning && (
            <div className="bg-gray-900/50 border border-gray-800/50 rounded-xl p-4 space-y-3 animate-fade-in">
              <input
                type="text"
                value={textDraft.title}
                onChange={(e) => setTextDraft((d) => ({ ...d, title: e.target.value }))}
                placeholder="Paper title (optional)"
                className="w-full bg-transparent border-b border-gray-700/50 text-sm text-gray-200 placeholder-gray-600 outline-none pb-1.5 focus:border-indigo-500/50 transition-colors"
              />
              <textarea
                value={textDraft.text}
                onChange={(e) => setTextDraft((d) => ({ ...d, text: e.target.value }))}
                placeholder="Paste the abstract, introduction, or full paper text here…"
                rows={6}
                className="w-full bg-gray-900/40 border border-gray-800/50 rounded-lg text-xs text-gray-300 placeholder-gray-600 outline-none p-3 resize-none focus:border-indigo-500/30 transition-colors leading-relaxed"
              />
              <button
                onClick={addTextPaper}
                disabled={!textDraft.text.trim()}
                className="btn-primary text-white text-xs py-2 px-5 disabled:opacity-40"
              >
                Add Paper
              </button>
            </div>
          )}

          {/* Status / error / run button */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{error}</p>
            </div>
          )}

          {isRunning && statusMsg && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin flex-shrink-0" />
              <p className="text-xs text-indigo-300">{statusMsg}</p>
            </div>
          )}

          <div className="flex items-center gap-3 pt-1">
            {isRunning ? (
              <button onClick={cancel} className="btn-danger text-white text-xs">
                Cancel
              </button>
            ) : (
              <button
                onClick={runAnalysis}
                disabled={papers.length === 0}
                className="btn-primary text-white text-xs disabled:opacity-40"
              >
                Analyze {papers.length > 0 ? `${papers.length} Paper${papers.length > 1 ? "s" : ""}` : "Papers"}
              </button>
            )}
            {papers.length > 0 && !isRunning && (
              <span className="text-xs text-gray-600">
                {papers.length} paper{papers.length > 1 ? "s" : ""} ready
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Done — show reset button ───────────────────────────────────────── */}
      {isDone && result && (
        <div className="flex items-center justify-between glass-card px-5 py-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-sm text-gray-300 font-medium">
              Analysis complete — {result.paper_count} paper{result.paper_count !== 1 ? "s" : ""} analyzed
            </span>
          </div>
          <button
            onClick={reset}
            className="text-xs text-gray-500 hover:text-indigo-400 flex items-center gap-1 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Analyze new papers
          </button>
        </div>
      )}

      {/* ── Per-paper analysis cards ───────────────────────────────────────── */}
      {result && result.paper_analyses.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 px-1">
            <div className="h-px flex-1 bg-gradient-to-r from-indigo-500/20 to-transparent" />
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">
              Individual Paper Analyses
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-indigo-500/20 to-transparent" />
          </div>
          {result.paper_analyses.map((a, i) => (
            <PaperAnalysisCard key={i} analysis={a} index={i} />
          ))}
        </div>
      )}

      {/* ── Comparative analysis ────────────────────────────────────────────── */}
      {result && result.comparative_analysis && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <div className="h-px flex-1 bg-gradient-to-r from-cyan-500/20 to-transparent" />
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">
              Comparative Analysis
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-cyan-500/20 to-transparent" />
          </div>
          <ComparativeAnalysis
            markdown={result.comparative_analysis}
            paperCount={result.paper_count}
          />
        </div>
      )}
    </div>
  );
}
