import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { analyzeQueryStream, exportAnalysis } from "../api";
import type { StepProgress } from "../api";
import AIRewrite from "../components/AIRewrite";
import MetricsCards from "../components/MetricsCards";
import PlanSummary from "../components/PlanSummary";
import ProgressStepper from "../components/ProgressStepper";
import QueryInput from "../components/QueryInput";
import QueryOverview from "../components/QueryOverview";
import Recommendations from "../components/Recommendations";
import TableAnalysis from "../components/TableAnalysis";
import WarehouseInfo from "../components/WarehouseInfo";
import type { AnalysisResult } from "../types";

const TABS = [
  "Overview",
  "Metrics",
  "Tables",
  "Plan",
  "Warehouse",
  "Recommendations",
  "AI Rewrite",
] as const;

type Tab = (typeof TABS)[number];

export default function AnalyzePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Overview");
  const [statementId, setStatementId] = useState(
    searchParams.get("statement_id") || "",
  );
  const [progress, setProgress] = useState<StepProgress | null>(null);
  const autoTriggered = useRef(false);

  const handleAnalyze = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      setResult(null);
      setProgress(null);
      setStatementId(id);

      setSearchParams({ statement_id: id }, { replace: true });

      await analyzeQueryStream(id, {
        onProgress: (p) => setProgress(p),
        onResult: (data) => {
          setResult(data);
          setTab("Overview");
          setLoading(false);
          setProgress(null);
        },
        onError: (msg) => {
          setError(msg);
          setLoading(false);
          setProgress(null);
        },
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (autoTriggered.current) return;
    const initial = searchParams.get("statement_id") || "";
    if (initial) {
      autoTriggered.current = true;
      handleAnalyze(initial);
    }
  }, [handleAnalyze, searchParams]);

  const handleExport = async (format: string) => {
    if (!statementId) return;
    try {
      const blob = await exportAnalysis(statementId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analysis_${statementId.slice(0, 8)}.${format === "html" ? "html" : format === "json" ? "json" : "md"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed");
    }
  };

  const recCount = result?.recommendations.length ?? 0;
  const tabPanelId = `tabpanel-${tab.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <>
      <div className="flex items-center justify-center py-3 px-6 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <QueryInput
          onSubmit={handleAnalyze}
          loading={loading}
          initialValue={statementId}
        />
      </div>

      {error && (
        <div
          className="flex items-center justify-between gap-3 max-w-5xl mx-auto mt-3 px-4 py-3 text-sm text-red-800 dark:text-red-300 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/30"
          role="alert"
        >
          <span>{error}</span>
          <button
            className="bg-transparent border-none text-red-800 dark:text-red-300 text-lg cursor-pointer px-1 leading-none opacity-60 hover:opacity-100 transition-opacity"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}

      {loading && (
        <div className="max-w-5xl mx-auto px-6 py-5" aria-busy="true">
          <ProgressStepper current={progress} />
        </div>
      )}

      {result && (
        <div
          className={`mx-auto px-6 py-5 transition-all ${tab === "AI Rewrite" ? "max-w-[1600px]" : "max-w-5xl"}`}
        >
          <div className="flex items-center justify-between mb-4">
            <nav
              className="flex border-b border-gray-200 dark:border-gray-700 overflow-x-auto scrollbar-hide flex-1"
              role="tablist"
              aria-label="Analysis sections"
            >
              {TABS.map((t) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  aria-controls={`tabpanel-${t.replace(/\s+/g, "-").toLowerCase()}`}
                  className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px cursor-pointer transition-colors ${
                    tab === t
                      ? "text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400 font-semibold"
                      : "text-gray-500 dark:text-gray-400 border-transparent hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300"
                  }`}
                  onClick={() => setTab(t)}
                >
                  {t}
                  {t === "Recommendations" && recCount > 0 && (
                    <span className="bg-red-600 text-white text-xs font-semibold px-2 py-0.5 rounded-full leading-tight">
                      {recCount}
                    </span>
                  )}
                </button>
              ))}
            </nav>
            <div className="flex items-center gap-1 ml-4 shrink-0">
              <button
                onClick={() => handleExport("markdown")}
                className="text-xs px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
              >
                Export MD
              </button>
              <button
                onClick={() => handleExport("html")}
                className="text-xs px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
              >
                Export HTML
              </button>
            </div>
          </div>

          <main role="tabpanel" id={tabPanelId} aria-label={tab}>
            {tab === "Overview" && (
              <QueryOverview metrics={result.query_metrics} />
            )}
            {tab === "Metrics" && (
              <MetricsCards metrics={result.query_metrics} />
            )}
            {tab === "Tables" && <TableAnalysis tables={result.tables} />}
            {tab === "Plan" &&
              (result.plan_summary ? (
                <PlanSummary plan={result.plan_summary} />
              ) : (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
                  <h2 className="text-base font-semibold mb-3 dark:text-white">Execution Plan</h2>
                  <p className="text-gray-500 dark:text-gray-400">
                    No execution plan available. EXPLAIN is only supported for SELECT statements.
                  </p>
                </div>
              ))}
            {tab === "Warehouse" &&
              (result.warehouse ? (
                <WarehouseInfo warehouse={result.warehouse} />
              ) : (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
                  <h2 className="text-base font-semibold mb-3 dark:text-white">Warehouse</h2>
                  <p className="text-gray-500 dark:text-gray-400">
                    No warehouse information available.
                  </p>
                </div>
              ))}
            {tab === "Recommendations" && (
              <Recommendations recommendations={result.recommendations} />
            )}
            {tab === "AI Rewrite" && (
              <AIRewrite
                statementId={statementId}
                warehouseId={result.query_metrics.warehouse_id ?? undefined}
              />
            )}
          </main>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="text-center py-24 px-8 text-gray-400 dark:text-gray-500">
          <p>Enter a statement ID above to begin analysis.</p>
        </div>
      )}
    </>
  );
}
