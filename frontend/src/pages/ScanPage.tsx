import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { scanQueryStream } from "../api";
import type { StepProgress } from "../api";
import ProgressStepper from "../components/ProgressStepper";
import type { ScanFilter, ScanResult, WorkloadPattern } from "../types";
import { formatNumber, humanBytes } from "../utils";

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

function HealthBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
      : score >= 50
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300"
        : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300";
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {score}
    </span>
  );
}

function PatternCard({ pattern }: { pattern: WorkloadPattern }) {
  const dotClass = SEVERITY_DOT[pattern.severity] || "bg-gray-400";
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
        <span className="font-semibold text-sm dark:text-white">{pattern.title}</span>
        <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">
          {pattern.affected_queries} queries
        </span>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-300">{pattern.description}</p>
    </div>
  );
}

export default function ScanPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ScanFilter>({
    max_results: 20,
  });
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<StepProgress | null>(null);

  const handleScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(null);

    await scanQueryStream(filters, {
      onProgress: (p) => setProgress(p),
      onResult: (data) => {
        setResult(data);
        setLoading(false);
        setProgress(null);
      },
      onError: (msg) => {
        setError(msg);
        setLoading(false);
        setProgress(null);
      },
    });
  }, [filters]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      <h1 className="text-xl font-bold mb-4 dark:text-white">Workload Scanner</h1>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5 mb-5">
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Warehouse ID
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              placeholder="Optional"
              value={filters.warehouse_id || ""}
              onChange={(e) =>
                setFilters((f) => ({ ...f, warehouse_id: e.target.value || undefined }))
              }
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              User
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              placeholder="Optional"
              value={filters.user_name || ""}
              onChange={(e) =>
                setFilters((f) => ({ ...f, user_name: e.target.value || undefined }))
              }
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Table name (contains)
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              placeholder="Optional"
              value={filters.table_name || ""}
              onChange={(e) =>
                setFilters((f) => ({ ...f, table_name: e.target.value || undefined }))
              }
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Min duration (ms)
            </label>
            <input
              type="number"
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              placeholder="e.g. 5000"
              value={filters.min_duration_ms ?? ""}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  min_duration_ms: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Max results
            </label>
            <input
              type="number"
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              value={filters.max_results ?? 20}
              onChange={(e) =>
                setFilters((f) => ({ ...f, max_results: Number(e.target.value) || 20 }))
              }
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleScan}
            disabled={loading}
            className="bg-blue-700 text-white font-medium text-sm px-5 py-2 rounded hover:bg-blue-800 disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Scanning..." : "Scan Workload"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 text-sm text-red-800 dark:text-red-300 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/30" role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className="py-5" aria-busy="true">
          <ProgressStepper current={progress} />
        </div>
      )}

      {result && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-3 mb-5">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Queries Scanned</div>
              <div className="text-2xl font-bold dark:text-white">
                {result.total_queries_scanned}
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Duration</div>
              <div className="text-2xl font-bold dark:text-white">
                {formatNumber(result.total_duration_ms)} ms
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Analyzed</div>
              <div className="text-2xl font-bold dark:text-white">{result.queries.length}</div>
            </div>
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Patterns Found</div>
              <div className="text-2xl font-bold dark:text-white">{result.patterns.length}</div>
            </div>
          </div>

          {/* Workload patterns */}
          {result.patterns.length > 0 && (
            <div className="mb-5">
              <h2 className="text-base font-semibold mb-3 dark:text-white">
                Workload Patterns
              </h2>
              <div className="flex flex-col gap-2">
                {result.patterns.map((p, i) => (
                  <PatternCard key={i} pattern={p} />
                ))}
              </div>
            </div>
          )}

          {/* Query table */}
          <h2 className="text-base font-semibold mb-3 dark:text-white">
            Query Results
          </h2>
          <div className="overflow-x-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">SQL</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Issues</th>
                  <th className="px-4 py-3">Top Issues</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {result.queries.map((q) => (
                  <tr
                    key={q.statement_id}
                    className="border-t border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-4 py-3">
                      <HealthBadge score={q.health_score} />
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <span className="font-mono text-xs text-gray-700 dark:text-gray-300 truncate block">
                        {q.statement_text.slice(0, 80)}
                        {q.statement_text.length > 80 ? "..." : ""}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      {q.total_duration_ms != null
                        ? `${formatNumber(q.total_duration_ms)} ms`
                        : "N/A"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {q.critical_count > 0 && (
                          <span className="flex items-center gap-0.5 text-xs text-red-600 dark:text-red-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                            {q.critical_count}
                          </span>
                        )}
                        {q.warning_count > 0 && (
                          <span className="flex items-center gap-0.5 text-xs text-amber-600 dark:text-amber-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                            {q.warning_count}
                          </span>
                        )}
                        {q.info_count > 0 && (
                          <span className="flex items-center gap-0.5 text-xs text-blue-600 dark:text-blue-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                            {q.info_count}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        {q.top_recommendations.slice(0, 2).map((t, i) => (
                          <span key={i} className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          navigate(`/?statement_id=${encodeURIComponent(q.statement_id)}`)
                        }
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <p>Configure filters above and click "Scan Workload" to analyze multiple queries.</p>
        </div>
      )}
    </div>
  );
}
