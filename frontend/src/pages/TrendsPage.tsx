import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  BarChart,
} from "recharts";
import { getHistory, getTrends } from "../api";
import type { AnalysisRecord, TrendPoint } from "../types";

function HealthScoreChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map((d) => ({
    ...d,
    time: new Date(d.analyzed_at).toLocaleDateString(),
  }));

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
      <h3 className="text-sm font-semibold mb-3 dark:text-white">Health Score Over Time</h3>
      {formatted.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">No data yet. Analyze some queries to see trends.</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={formatted}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <Tooltip
              contentStyle={{
                background: "white",
                border: "1px solid #e5e7eb",
                borderRadius: 6,
                fontSize: 12,
              }}
            />
            <Line
              type="monotone"
              dataKey="health_score"
              stroke="#2563eb"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Health Score"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function RecommendationCountChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map((d) => ({
    ...d,
    time: new Date(d.analyzed_at).toLocaleDateString(),
  }));

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
      <h3 className="text-sm font-semibold mb-3 dark:text-white">Recommendation Count Over Time</h3>
      {formatted.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">No data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={formatted}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <Tooltip
              contentStyle={{
                background: "white",
                border: "1px solid #e5e7eb",
                borderRadius: 6,
                fontSize: 12,
              }}
            />
            <Bar dataKey="recommendation_count" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Issues" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function TrendsPage() {
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [history, setHistory] = useState<AnalysisRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getTrends(), getHistory()])
      .then(([t, h]) => {
        setTrends(t);
        setHistory(h);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      <h1 className="text-xl font-bold mb-4 dark:text-white">Trends & History</h1>

      {loading ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 mb-5">
            <HealthScoreChart data={trends} />
            <RecommendationCountChart data={trends} />
          </div>

          <h2 className="text-base font-semibold mb-3 dark:text-white">Analysis History</h2>
          <div className="overflow-x-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3">Statement ID</th>
                  <th className="px-4 py-3">Analyzed</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Issues</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">SQL</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">
                      No analysis history yet.
                    </td>
                  </tr>
                )}
                {history.map((h, i) => (
                  <tr
                    key={`${h.statement_id}-${i}`}
                    className="border-t border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                      {h.statement_id.slice(0, 12)}...
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      {new Date(h.analyzed_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          h.health_score >= 80
                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                            : h.health_score >= 50
                              ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300"
                              : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
                        }`}
                      >
                        {h.health_score}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {h.critical_count > 0 && (
                          <span className="text-xs text-red-600 dark:text-red-400">{h.critical_count}C</span>
                        )}
                        {h.warning_count > 0 && (
                          <span className="text-xs text-amber-600 dark:text-amber-400">{h.warning_count}W</span>
                        )}
                        {h.info_count > 0 && (
                          <span className="text-xs text-blue-600 dark:text-blue-400">{h.info_count}I</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-300 text-xs">
                      {h.total_duration_ms != null ? `${h.total_duration_ms.toLocaleString()} ms` : "N/A"}
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <span className="font-mono text-xs text-gray-500 dark:text-gray-400 truncate block">
                        {h.statement_text.slice(0, 60)}...
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
