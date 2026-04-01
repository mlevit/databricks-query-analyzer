import { useEffect, useRef, useState } from "react";
import type { AnalysisResult } from "../types";
import { downloadMarkdown, downloadHtml } from "../exportReport";

interface Props {
  result: AnalysisResult;
}

export default function ExportMenu({ result }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-white/[0.08] bg-white/[0.04] text-slate-400 hover:bg-white/[0.08] hover:text-slate-200 cursor-pointer transition-colors"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        Export
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 10 6">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 1l4 4 4-4" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-48 rounded-xl border border-white/[0.08] bg-[#0c1029] shadow-xl shadow-black/40 z-50 overflow-hidden animate-in fade-in slide-in-from-top-1">
          <div className="py-1">
            <button
              onClick={() => { downloadMarkdown(result); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-slate-300 hover:bg-white/[0.06] hover:text-white cursor-pointer bg-transparent border-none text-left transition-colors"
            >
              <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <div>
                <div className="font-medium">Markdown</div>
                <div className="text-[0.65rem] text-slate-500">.md — for Slack, GitHub</div>
              </div>
            </button>
            <button
              onClick={() => { downloadHtml(result); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-slate-300 hover:bg-white/[0.06] hover:text-white cursor-pointer bg-transparent border-none text-left transition-colors"
            >
              <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
              </svg>
              <div>
                <div className="font-medium">HTML</div>
                <div className="text-[0.65rem] text-slate-500">.html — styled, for email</div>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
