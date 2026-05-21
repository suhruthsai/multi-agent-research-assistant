"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, FileText, FlaskConical, BookOpen } from "lucide-react";

type Paper     = { title:string; abstract:string; authors:string[]; year:number; url:string; source:string; citation_count:number; relevance_score:number };
type Hypothesis= { hypothesis:string; justification:string; confidence:number };
type Tab       = "report" | "hypotheses" | "papers";

interface Props { report:string; synthesis:string; hypotheses:Hypothesis[]; papers:Paper[]; confidence_score:number }

export default function ReportViewer({ report, synthesis, hypotheses, papers, confidence_score }: Props) {
  const [tab, setTab]       = useState<Tab>("report");
  const [copied, setCopied] = useState(false);

  const copy = () => { navigator.clipboard.writeText(report); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  const tabs = [
    { key: "report"     as Tab, label: "Report",     icon: <FileText size={13} /> },
    { key: "hypotheses" as Tab, label: "Hypotheses", icon: <FlaskConical size={13} />, count: hypotheses.length },
    { key: "papers"     as Tab, label: "Papers",     icon: <BookOpen size={13} />,     count: papers.length },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex gap-1">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                ${tab === t.key ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"}`}>
              {t.icon} {t.label}
              {t.count != null && (
                <span className={`text-xs px-1.5 rounded-full ${tab === t.key ? "bg-indigo-500" : "bg-gray-700 text-gray-400"}`}>
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span>Confidence</span>
            <div className="w-14 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${confidence_score >= 0.75 ? "bg-emerald-500" : confidence_score >= 0.5 ? "bg-yellow-500" : "bg-red-500"}`}
                style={{ width: `${Math.round(confidence_score * 100)}%` }} />
            </div>
            <span className="text-gray-300">{Math.round(confidence_score * 100)}%</span>
          </div>
          {tab === "report" && (
            <button onClick={copy} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white px-2 py-1 rounded-lg hover:bg-gray-800 transition-all">
              {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              {copied ? "Copied" : "Copy"}
            </button>
          )}
        </div>
      </div>

      <div className="p-5 max-h-[68vh] overflow-y-auto">
        {tab === "report" && (
          <div className="report-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        )}

        {tab === "hypotheses" && (
          <div className="space-y-3">
            {hypotheses.length === 0 && <p className="text-gray-600 text-sm">No hypotheses generated.</p>}
            {hypotheses.map((h, i) => (
              <div key={i} className="border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs font-mono text-indigo-400 bg-indigo-400/10 px-2 py-0.5 rounded-full">H{i + 1}</span>
                  <div className="flex items-center gap-1.5 text-xs text-gray-500 shrink-0">
                    <div className="w-10 h-1 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full bg-pink-500 rounded-full" style={{ width: `${Math.round((h.confidence ?? 0) * 100)}%` }} />
                    </div>
                    {Math.round((h.confidence ?? 0) * 100)}%
                  </div>
                </div>
                <p className="text-white font-medium text-sm mb-2">{h.hypothesis}</p>
                <p className="text-gray-400 text-xs leading-relaxed">{h.justification}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "papers" && (
          <div className="space-y-3">
            {papers.length === 0 && <p className="text-gray-600 text-sm">No papers retrieved.</p>}
            {papers.map((p, i) => (
              <a key={i} href={p.url} target="_blank" rel="noopener noreferrer"
                className="block border border-gray-800 rounded-xl p-4 hover:border-indigo-700 hover:bg-gray-800/50 transition-all">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <h3 className="text-sm font-medium text-white leading-snug">{p.title}</h3>
                  <span className="text-xs text-gray-500 shrink-0 bg-gray-800 px-2 py-0.5 rounded-full">{p.year || "n/a"}</span>
                </div>
                <p className="text-xs text-gray-500 mb-2">{p.authors.slice(0, 3).join(", ")}{p.authors.length > 3 ? " et al." : ""}</p>
                <p className="text-xs text-gray-400 line-clamp-2">{p.abstract}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                    ${p.source === "arxiv" ? "bg-orange-400/10 text-orange-400" :
                      p.source === "semantic_scholar" ? "bg-blue-400/10 text-blue-400" : "bg-gray-700 text-gray-400"}`}>
                    {p.source}
                  </span>
                  <span className="text-xs text-gray-600">{p.citation_count} citations</span>
                  {p.relevance_score > 0 && <span className="text-xs text-gray-600">relevance {Math.round(p.relevance_score * 100)}%</span>}
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}