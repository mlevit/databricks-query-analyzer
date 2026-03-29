import { useCallback, useState } from "react";
import { scanTables } from "../api";
import TableAnalysis from "../components/TableAnalysis";
import type { TableHealthResult, TableHealthScanFilter } from "../types";

export default function TablesPage() {
  const [filters, setFilters] = useState<TableHealthScanFilter>({
    catalog: "",
    schema_name: "",
    max_results: 50,
  });
  const [result, setResult] = useState<TableHealthResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScan = useCallback(async () => {
    if (!filters.catalog || !filters.schema_name) {
      setError("Catalog and schema are required.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await scanTables(filters);
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Table scan failed");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      <h1 className="text-xl font-bold mb-4 dark:text-white">Table Health</h1>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5 mb-5">
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Catalog *
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              value={filters.catalog}
              onChange={(e) => setFilters((f) => ({ ...f, catalog: e.target.value }))}
              placeholder="e.g. main"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Schema *
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              value={filters.schema_name}
              onChange={(e) =>
                setFilters((f) => ({ ...f, schema_name: e.target.value }))
              }
              placeholder="e.g. default"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Table pattern
            </label>
            <input
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              value={filters.table_name_pattern || ""}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  table_name_pattern: e.target.value || undefined,
                }))
              }
              placeholder="e.g. fact_%"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Max tables
            </label>
            <input
              type="number"
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2.5 py-2 text-sm"
              value={filters.max_results ?? 50}
              onChange={(e) =>
                setFilters((f) => ({ ...f, max_results: Number(e.target.value) || 50 }))
              }
            />
          </div>
        </div>
        <div className="mt-4">
          <button
            onClick={handleScan}
            disabled={loading}
            className="bg-blue-700 text-white font-medium text-sm px-5 py-2 rounded hover:bg-blue-800 disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Scanning..." : "Scan Tables"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 text-sm text-red-800 dark:text-red-300 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/30" role="alert">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="mb-4 text-sm text-gray-500 dark:text-gray-400">
            Scanned {result.total_scanned} tables
          </div>
          <TableAnalysis tables={result.tables} />
        </>
      )}

      {!result && !loading && !error && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <p>Enter a catalog and schema above to scan table health.</p>
        </div>
      )}
    </div>
  );
}
