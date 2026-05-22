"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ClipboardList } from "lucide-react";

interface ResearchPlanViewProps {
  plan: string;
}

export default function ResearchPlanView({ plan }: ResearchPlanViewProps) {
  if (!plan || plan.trim().length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 text-sm">No research plan available.</p>
        <p className="text-gray-700 text-xs mt-1">
          The planner agent creates a structured research plan before searching.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-2 animate-fade-in">
      <div className="flex items-center gap-2 mb-4">
        <span className="w-7 h-7 rounded-lg bg-sky-500/20 flex items-center justify-center">
          <ClipboardList className="w-3.5 h-3.5 text-sky-400" />
        </span>
        <h3 className="text-sm font-semibold text-gray-300">Research Plan</h3>
      </div>
      <div className="report-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{plan}</ReactMarkdown>
      </div>
    </div>
  );
}
