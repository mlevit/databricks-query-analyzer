import { useCallback, useState } from "react";
import { analyzeSql } from "../api";
import Recommendations from "../components/Recommendations";
import type { RawSQLResult } from "../types";

export default function SqlAnalyzePage() {
  const [sql, setSql] = useState("");
  const [result, setResult] = useState<RawSQLResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async () => {
    if (!sql.trim()) {
      setError("Please enter SQL to analyze.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeSql(sql);
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [sql]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-5">
      <h1 className="text-xl font-bold mb-4 dark:text-white">SQL Analyzer</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Paste SQL to analyze for anti-patterns without needing a statement ID or execution history.
      </p>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5 mb-5">
        <textarea
          className="w-full h-48 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-3 py-2 text-sm font-mono resize-y"
          placeholder="SELECT * FROM ..."
          value={sql}
          onChange={(e) => setSql(e.target.value)}
        />
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="bg-blue-700 text-white font-medium text-sm px-5 py-2 rounded hover:bg-blue-800 disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Analyzing..." : "Analyze SQL"}
          </button>
          {result && (
            <span
              className={`text-sm font-semibold ${
                result.health_score >= 80
                  ? "text-green-600 dark:text-green-400"
                  : result.health_score >= 50
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-red-600 dark:text-red-400"
              }`}
            >
              Health Score: {result.health_score}/100
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 text-sm text-red-800 dark:text-red-300 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/30" role="alert">
          {error}
        </div>
      )}

      {result && (
        <>
          {result.tables_referenced.length > 0 && (
            <div className="mb-4 text-sm text-gray-600 dark:text-gray-400">
              <strong>Tables referenced:</strong>{" "}
              {result.tables_referenced.map((t, i) => (
                <span key={t}>
                  <code className="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs font-mono">
                    {t}
                  </code>
                  {i < result.tables_referenced.length - 1 ? ", " : ""}
                </span>
              ))}
            </div>
          )}
          <Recommendations recommendations={result.recommendations} />
        </>
      )}

      {!result && !loading && !error && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <p>Paste SQL above and click "Analyze SQL" to check for anti-patterns.</p>
        </div>
      )}
    </div>
  );
}
