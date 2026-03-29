import { useEffect, useState } from "react";
import { getWarehouses } from "../api";
import { RecommendationCard } from "../components/shared/recommendation";
import type { WarehouseFleetResult, WarehouseInfo as WI } from "../types";

function WarehouseCard({ wh }: { wh: WI }) {
  const [expanded, setExpanded] = useState(false);
  const recCount = wh.recommendations.length;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm dark:text-white">{wh.name || wh.warehouse_id}</h3>
          {wh.enable_photon && (
            <span className="text-xs bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 px-2 py-0.5 rounded-full">
              Photon
            </span>
          )}
          {wh.warehouse_type && (
            <span className="text-xs bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 px-2 py-0.5 rounded-full">
              {wh.warehouse_type}
            </span>
          )}
        </div>
        {recCount > 0 && (
          <span className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 px-2 py-0.5 rounded-full">
            {recCount} issue{recCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-2 text-xs">
        <div>
          <span className="text-gray-500 dark:text-gray-400">Size:</span>{" "}
          <span className="text-gray-700 dark:text-gray-300">{wh.cluster_size || "N/A"}</span>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Clusters:</span>{" "}
          <span className="text-gray-700 dark:text-gray-300">{wh.num_clusters ?? "N/A"}</span>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Channel:</span>{" "}
          <span className="text-gray-700 dark:text-gray-300">{wh.channel || "N/A"}</span>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Spot:</span>{" "}
          <span className="text-gray-700 dark:text-gray-300">{wh.spot_instance_policy || "N/A"}</span>
        </div>
      </div>

      {recCount > 0 && (
        <>
          <button
            className="mt-2 text-xs text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Hide recommendations" : `Show ${recCount} recommendation${recCount > 1 ? "s" : ""}`}
          </button>
          {expanded && (
            <div className="mt-2 flex flex-col gap-1.5">
              {wh.recommendations.map((r, i) => (
                <RecommendationCard key={i} recommendation={r} variant="compact" />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function WarehousesPage() {
  const [result, setResult] = useState<WarehouseFleetResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWarehouses()
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      <h1 className="text-xl font-bold mb-4 dark:text-white">Warehouse Fleet</h1>

      {loading && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">Loading warehouses...</div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 text-sm text-red-800 dark:text-red-300 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/30" role="alert">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="mb-4 text-sm text-gray-500 dark:text-gray-400">
            {result.warehouses.length} warehouse{result.warehouses.length !== 1 ? "s" : ""}
          </div>
          <div className="grid grid-cols-1 gap-3">
            {result.warehouses.map((wh) => (
              <WarehouseCard key={wh.warehouse_id} wh={wh} />
            ))}
          </div>
        </>
      )}

      {result && result.warehouses.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          No warehouses found.
        </div>
      )}
    </div>
  );
}
