"use client";
import { useState, useEffect, useCallback } from "react";
import {
  X,
  Clock,
  FileText,
  Trash2,
  ChevronRight,
  Loader2,
  History,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HistoryItem = {
  id: string;
  query: string;
  confidence_score: number;
  paper_count: number;
  pdf_processed_count: number;
  created_at: string;
};

interface HistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadReport: (data: any) => void;
}

export default function HistorySidebar({
  isOpen,
  onClose,
  onLoadReport,
}: HistorySidebarProps) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  // Fetch history when sidebar opens
  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    fetch(`${API_URL}/history`)
      .then((r) => r.json())
      .then((data) => setItems(data))
      .catch((err) => console.error("Failed to fetch history:", err))
      .finally(() => setLoading(false));
  }, [isOpen]);

  // Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Load a full report
  const handleLoad = useCallback(
    async (id: string) => {
      setLoadingId(id);
      try {
        const res = await fetch(`${API_URL}/history/${id}`);
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        onLoadReport(data);
        onClose();
      } catch (err) {
        console.error("Failed to load report:", err);
      } finally {
        setLoadingId(null);
      }
    },
    [onLoadReport, onClose]
  );

  // Delete a report
  const handleDelete = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await fetch(`${API_URL}/history/${id}`, { method: "DELETE" });
        setItems((prev) => prev.filter((item) => item.id !== id));
      } catch (err) {
        console.error("Failed to delete report:", err);
      }
    },
    []
  );

  // Format date
  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    const hrs = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    if (hrs < 24) return `${hrs}h ago`;
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed left-0 top-0 bottom-0 z-50 w-full max-w-sm animate-fade-in">
        <div
          className="h-full bg-gray-950 border-r border-gray-800/50 flex flex-col shadow-2xl"
          style={{ animation: "slideInLeft 0.3s ease-out" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-800/50">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-gray-300">
                Research History
              </h3>
              {items.length > 0 && (
                <span className="text-[10px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded-full">
                  {items.length}
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-6">
                <FileText className="w-8 h-8 text-gray-700 mb-3" />
                <p className="text-sm text-gray-500">No research history yet</p>
                <p className="text-xs text-gray-600 mt-1">
                  Your completed research reports will appear here
                </p>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {items.map((item, i) => (
                  <div
                    key={item.id}
                    onClick={() => handleLoad(item.id)}
                    className="group p-3 rounded-xl cursor-pointer transition-all duration-200
                               hover:bg-gray-900/80 border border-transparent hover:border-gray-800/50
                               animate-fade-in"
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-300 truncate leading-snug">
                          {item.query}
                        </p>
                        <div className="flex items-center gap-3 mt-1.5">
                          <span className="flex items-center gap-1 text-[10px] text-gray-600">
                            <Clock className="w-3 h-3" />
                            {formatDate(item.created_at)}
                          </span>
                          <span className="text-[10px] text-gray-600">
                            {item.paper_count} papers
                          </span>
                          {item.confidence_score > 0 && (
                            <span className="text-[10px] text-indigo-400/60 font-mono">
                              {Math.round(item.confidence_score * 100)}%
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {loadingId === item.id ? (
                          <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                        ) : (
                          <>
                            <button
                              onClick={(e) => handleDelete(item.id, e)}
                              className="p-1 rounded text-gray-700 hover:text-red-400 
                                         opacity-0 group-hover:opacity-100 transition-all"
                              title="Delete"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                            <ChevronRight className="w-3.5 h-3.5 text-gray-700 group-hover:text-gray-500 transition-colors" />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Slide-in animation */}
      <style jsx>{`
        @keyframes slideInLeft {
          from {
            transform: translateX(-100%);
          }
          to {
            transform: translateX(0);
          }
        }
      `}</style>
    </>
  );
}
