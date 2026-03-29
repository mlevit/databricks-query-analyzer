import type {
  WarehouseInfo as WarehouseInfoType,
  WarehouseActivity,
  ScalingEvent,
  QueryLoadPoint,
} from "../types";
import { RecommendationCard } from "./shared/recommendation";

interface Props {
  warehouse: WarehouseInfoType;
}

const EVENT_COLORS: Record<string, string> = {
  SCALED_UP: "#16a34a",
  SCALED_DOWN: "#d97706",
  RUNNING: "#2563eb",
  STARTING: "#2563eb",
  STOPPING: "#6b7280",
  STOPPED: "#6b7280",
};

const EVENT_TYPE_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  SCALED_UP: { bg: "bg-green-50", text: "text-green-700", ring: "ring-green-600/20" },
  SCALED_DOWN: { bg: "bg-amber-50", text: "text-amber-700", ring: "ring-amber-600/20" },
  RUNNING: { bg: "bg-blue-50", text: "text-blue-700", ring: "ring-blue-600/20" },
  STARTING: { bg: "bg-blue-50", text: "text-blue-700", ring: "ring-blue-600/20" },
  STOPPING: { bg: "bg-gray-50", text: "text-gray-600", ring: "ring-gray-500/20" },
  STOPPED: { bg: "bg-gray-50", text: "text-gray-600", ring: "ring-gray-500/20" },
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatTimeShort(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function parseTs(iso: string): number {
  return new Date(iso).getTime();
}

// ─── Chart ──────────────────────────────────────────────────────────────────

const CHART_W = 700;
const CHART_H = 200;
const PAD = { top: 20, right: 50, bottom: 32, left: 40 };
const PLOT_W = CHART_W - PAD.left - PAD.right;
const PLOT_H = CHART_H - PAD.top - PAD.bottom;

function ActivityChart({
  activity,
}: {
  activity: WarehouseActivity;
}) {
  const hasLoad = activity.query_load.length > 0;
  const hasScaling = activity.scaling_events.length > 0;
  if (!hasLoad && !hasScaling) return null;

  const tMin = computeTMin(activity);
  const tMax = computeTMax(activity);
  const tRange = tMax - tMin || 1;

  const x = (ts: number) => PAD.left + ((ts - tMin) / tRange) * PLOT_W;

  // Query execution window
  const qStart = parseTs(activity.time_window_start);
  const qEnd = parseTs(activity.time_window_end);
  const qX1 = Math.max(x(qStart), PAD.left);
  const qX2 = Math.min(x(qEnd), PAD.left + PLOT_W);

  // Y-axis left: query load (stacked bar: running + queued)
  const maxLoad = hasLoad
    ? Math.max(...activity.query_load.map((p) => p.running), 1)
    : 1;
  const yLoadCeil = niceMax(maxLoad);
  const yLoad = (v: number) => PAD.top + PLOT_H - (v / yLoadCeil) * PLOT_H;

  // Y-axis right: cluster count (line)
  const maxCluster = hasScaling
    ? Math.max(...activity.scaling_events.map((e) => e.cluster_count), 1)
    : 1;
  const yClusterCeil = niceMax(maxCluster);
  const yCluster = (v: number) => PAD.top + PLOT_H - (v / yClusterCeil) * PLOT_H;

  // Bar width
  const barGap = 1;
  const barW = hasLoad
    ? Math.max(2, Math.min(24, PLOT_W / activity.query_load.length - barGap))
    : 0;

  const clusterPath = buildStepPath(activity.scaling_events, x, yCluster, tMax);

  const ticks = computeXTicks(tMin, tMax, 6);
  const yLoadTicks = computeYTicks(yLoadCeil);
  const yClusterTicks = computeYTicks(yClusterCeil);

  return (
    <svg
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      className="w-full"
      style={{ maxHeight: 240 }}
      role="img"
      aria-label="Warehouse activity chart"
    >
      <defs>
        <clipPath id="plot-clip">
          <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} />
        </clipPath>
      </defs>

      {/* Query execution window highlight */}
      <rect
        x={qX1}
        y={PAD.top}
        width={Math.max(qX2 - qX1, 2)}
        height={PLOT_H}
        fill="#3b82f6"
        opacity={0.08}
      />
      <line x1={qX1} x2={qX1} y1={PAD.top} y2={PAD.top + PLOT_H} stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4,3" />
      <line x1={qX2} x2={qX2} y1={PAD.top} y2={PAD.top + PLOT_H} stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4,3" />
      <text x={qX1 + 3} y={PAD.top + 10} className="text-[7px] fill-blue-500 font-semibold">
        Query start
      </text>
      <text x={qX2 - 3} y={PAD.top + 10} textAnchor="end" className="text-[7px] fill-blue-500 font-semibold">
        Query end
      </text>

      {/* Grid lines */}
      {yLoadTicks.map((v) => (
        <line
          key={`g-${v}`}
          x1={PAD.left}
          x2={CHART_W - PAD.right}
          y1={yLoad(v)}
          y2={yLoad(v)}
          stroke="#e5e7eb"
          strokeDasharray="3,3"
        />
      ))}

      {/* Stacked bars: running (blue) with queued portion (orange) */}
      <g clipPath="url(#plot-clip)">
        {activity.query_load.map((pt, i) => {
          const cx = x(parseTs(pt.time));
          const totalH = (pt.running / yLoadCeil) * PLOT_H;
          const queuedH = (pt.queued / yLoadCeil) * PLOT_H;
          const runningH = totalH - queuedH;
          const barTop = PAD.top + PLOT_H - totalH;
          return (
            <g key={i}>
              {/* Running portion (bottom) */}
              <rect
                x={cx - barW / 2}
                y={barTop + queuedH}
                width={barW}
                height={Math.max(runningH, 0)}
                rx={1}
                fill="#93c5fd"
                opacity={0.75}
              />
              {/* Queued portion (top) */}
              {pt.queued > 0 && (
                <rect
                  x={cx - barW / 2}
                  y={barTop}
                  width={barW}
                  height={queuedH}
                  rx={1}
                  fill="#fb923c"
                  opacity={0.8}
                />
              )}
              <title>{`${formatTimeShort(pt.time)}: ${pt.running} total (${pt.running - pt.queued} running, ${pt.queued} queued)`}</title>
            </g>
          );
        })}
      </g>

      {/* Stepped line: cluster count */}
      {clusterPath && (
        <path d={clusterPath} fill="none" stroke="#f59e0b" strokeWidth={2} clipPath="url(#plot-clip)" />
      )}

      {/* Event markers */}
      {activity.scaling_events
        .filter((e) => e.event_type === "SCALED_UP" || e.event_type === "SCALED_DOWN")
        .map((ev, i) => {
          const cx = x(parseTs(ev.event_time));
          const cy = yCluster(ev.cluster_count);
          const color = EVENT_COLORS[ev.event_type] ?? "#6b7280";
          return (
            <g key={`m-${i}`}>
              <circle cx={cx} cy={cy} r={4} fill={color} stroke="#fff" strokeWidth={1.5} />
              <title>{`${ev.event_type} → ${ev.cluster_count} clusters at ${formatTime(ev.event_time)}`}</title>
            </g>
          );
        })}

      {/* X-axis */}
      <line
        x1={PAD.left}
        x2={CHART_W - PAD.right}
        y1={PAD.top + PLOT_H}
        y2={PAD.top + PLOT_H}
        stroke="#d1d5db"
      />
      {ticks.map((t) => (
        <text
          key={t}
          x={x(t)}
          y={PAD.top + PLOT_H + 16}
          textAnchor="middle"
          className="text-[9px] fill-gray-400"
        >
          {formatTimeShort(new Date(t).toISOString())}
        </text>
      ))}

      {/* Y-axis left: query load */}
      {yLoadTicks.map((v) => (
        <text
          key={`yl-${v}`}
          x={PAD.left - 6}
          y={yLoad(v) + 3}
          textAnchor="end"
          className="text-[9px] fill-gray-400"
        >
          {v}
        </text>
      ))}
      <text
        x={PAD.left - 6}
        y={PAD.top - 6}
        textAnchor="end"
        className="text-[8px] fill-blue-400 font-medium"
      >
        Queries
      </text>

      {/* Y-axis right: cluster count */}
      {hasScaling &&
        yClusterTicks.map((v) => (
          <text
            key={`yr-${v}`}
            x={CHART_W - PAD.right + 6}
            y={yCluster(v) + 3}
            textAnchor="start"
            className="text-[9px] fill-gray-400"
          >
            {v}
          </text>
        ))}
      {hasScaling && (
        <text
          x={CHART_W - PAD.right + 6}
          y={PAD.top - 6}
          textAnchor="start"
          className="text-[8px] fill-amber-500 font-medium"
        >
          Clusters
        </text>
      )}
    </svg>
  );
}

function computeTMin(a: WarehouseActivity): number {
  const candidates = [parseTs(a.time_window_start)];
  if (a.query_load.length) candidates.push(parseTs(a.query_load[0].time));
  if (a.scaling_events.length) candidates.push(parseTs(a.scaling_events[0].event_time));
  return Math.min(...candidates);
}

function computeTMax(a: WarehouseActivity): number {
  const candidates = [parseTs(a.time_window_end)];
  if (a.query_load.length) candidates.push(parseTs(a.query_load[a.query_load.length - 1].time) + 60_000);
  if (a.scaling_events.length)
    candidates.push(parseTs(a.scaling_events[a.scaling_events.length - 1].event_time));
  return Math.max(...candidates);
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  if (v <= 5) return v;
  const magnitude = Math.pow(10, Math.floor(Math.log10(v)));
  const norm = v / magnitude;
  if (norm <= 1) return magnitude;
  if (norm <= 2) return 2 * magnitude;
  if (norm <= 5) return 5 * magnitude;
  return 10 * magnitude;
}

function computeXTicks(tMin: number, tMax: number, count: number): number[] {
  const step = (tMax - tMin) / (count - 1);
  return Array.from({ length: count }, (_, i) => tMin + step * i);
}

function computeYTicks(ceil: number): number[] {
  if (ceil <= 1) return [0, 1];
  const step = ceil <= 4 ? 1 : ceil <= 10 ? 2 : Math.ceil(ceil / 5);
  const ticks: number[] = [];
  for (let v = 0; v <= ceil; v += step) ticks.push(v);
  return ticks;
}

function buildStepPath(
  events: ScalingEvent[],
  x: (ts: number) => number,
  y: (v: number) => number,
  tMax: number,
): string | null {
  if (!events.length) return null;
  const parts: string[] = [];
  for (let i = 0; i < events.length; i++) {
    const cx = x(parseTs(events[i].event_time));
    const cy = y(events[i].cluster_count);
    if (i === 0) {
      parts.push(`M${cx},${cy}`);
    } else {
      parts.push(`H${cx}`);
      parts.push(`V${cy}`);
    }
  }
  // Extend to end of chart
  const lastY = y(events[events.length - 1].cluster_count);
  parts.push(`H${x(tMax)}`);
  parts.push(`V${lastY}`);
  return parts.join(" ");
}

// ─── Activity card ─────────────────────────────────────────────────────────

function ActivityCard({ activity }: { activity: WarehouseActivity }) {
  const stats: { label: string; value: string }[] = [
    {
      label: "Concurrent Queries",
      value: activity.concurrent_query_count.toString(),
    },
    {
      label: "Queued Queries",
      value: activity.queued_query_count.toString(),
    },
    {
      label: "Total in Window",
      value: activity.total_queries_in_window.toString(),
    },
    {
      label: "Active Clusters",
      value: activity.active_cluster_count?.toString() ?? "N/A",
    },
  ];

  const hasChart = activity.query_load.length > 0 || activity.scaling_events.length > 0;
  const hasEvents = activity.scaling_events.length > 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <h2 className="text-base font-semibold mb-3">Activity During Query</h2>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3 mb-4">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col">
            <span className="text-[0.68rem] uppercase tracking-wide text-gray-400 font-medium">
              {s.label}
            </span>
            <span className="font-semibold text-sm">{s.value}</span>
          </div>
        ))}
      </div>

      {hasChart && (
        <div className="mb-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-2">
            <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
              <span className="w-3 h-2.5 rounded-sm bg-blue-300 opacity-75" />
              Running
            </span>
            <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
              <span className="w-3 h-2.5 rounded-sm bg-orange-400 opacity-80" />
              Queued
            </span>
            {hasEvents && (
              <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
                <span className="w-3 h-0.5 bg-amber-400 inline-block" />
                Cluster count
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
              <span className="w-2 h-2 rounded-full bg-green-600 inline-block" />
              Scale up
            </span>
            <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
              <span className="w-2 h-2 rounded-full bg-amber-600 inline-block" />
              Scale down
            </span>
            <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-gray-500">
              <span className="w-4 h-2.5 bg-blue-500/10 border border-dashed border-blue-400 inline-block rounded-sm" />
              Query window
            </span>
          </div>
          <ActivityChart activity={activity} />
        </div>
      )}

      <h3 className="text-sm font-medium text-gray-700 mb-2">Scaling Events</h3>
      {!hasEvents ? (
        <p className="text-sm text-gray-400">No scaling events during this period.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[0.68rem] uppercase tracking-wide text-gray-400 font-medium">
                <th className="pb-1.5 pr-4 font-medium">Time</th>
                <th className="pb-1.5 pr-4 font-medium">Event</th>
                <th className="pb-1.5 font-medium">Clusters</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {activity.scaling_events.map((ev, i) => {
                const style = EVENT_TYPE_STYLES[ev.event_type] ?? {
                  bg: "bg-gray-50",
                  text: "text-gray-600",
                  ring: "ring-gray-500/20",
                };
                return (
                  <tr key={i}>
                    <td className="py-1.5 pr-4 font-mono text-xs text-gray-600">
                      {formatTime(ev.event_time)}
                    </td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
                      >
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="py-1.5 font-semibold">{ev.cluster_count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function WarehouseInfo({ warehouse }: Props) {
  const isServerless = warehouse.enable_serverless_compute === true;

  const photonValue =
    warehouse.enable_photon === true
      ? "Enabled"
      : warehouse.enable_photon === false
        ? "Disabled"
        : "Unknown";

  const autoStopValue =
    warehouse.auto_stop_mins === 0
      ? "Disabled"
      : warehouse.auto_stop_mins != null
        ? `${warehouse.auto_stop_mins} min`
        : "N/A";

  const details: { label: string; value: string }[] = [
    { label: "Name", value: warehouse.name || "N/A" },
    { label: "Type", value: warehouse.warehouse_type || "N/A" },
    { label: "Size", value: warehouse.cluster_size || "N/A" },
    { label: "Min Clusters", value: warehouse.min_num_clusters?.toString() || "N/A" },
    { label: "Max Clusters", value: warehouse.max_num_clusters?.toString() || "N/A" },
    { label: "Running Clusters", value: warehouse.num_clusters?.toString() || "N/A" },
    { label: "Auto Stop", value: autoStopValue },
    { label: "Photon", value: photonValue },
    { label: "Spot Policy", value: warehouse.spot_instance_policy || "N/A" },
    { label: "Channel", value: warehouse.channel || "N/A" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-base font-semibold">Warehouse Configuration</h2>
          {isServerless && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-semibold text-green-700 ring-1 ring-inset ring-green-600/20">
              <svg
                className="h-3 w-3 text-green-500"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                  clipRule="evenodd"
                />
              </svg>
              Serverless
            </span>
          )}
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3 mb-3">
          {details.map((d) => (
            <div key={d.label} className="flex flex-col">
              <span className="text-[0.68rem] uppercase tracking-wide text-gray-400 font-medium">
                {d.label}
              </span>
              <span className="font-semibold text-sm">{d.value}</span>
            </div>
          ))}
        </div>
      </div>

      {warehouse.activity && <ActivityCard activity={warehouse.activity} />}

      {warehouse.recommendations.length > 0 && (
        <div className="flex flex-col gap-2">
          {warehouse.recommendations.map((r, i) => (
            <RecommendationCard key={i} recommendation={r} variant="compact" />
          ))}
        </div>
      )}
    </div>
  );
}
