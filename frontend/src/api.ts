import type {
  AIRewriteResult,
  AnalysisRecord,
  AnalysisResult,
  AnnotationStatus,
  BenchmarkResult,
  RawSQLResult,
  RecommendationAnnotation,
  ScanFilter,
  ScanResult,
  TableHealthResult,
  TableHealthScanFilter,
  TrendPoint,
  WarehouseFleetResult,
} from "./types";

const BASE = "/api";

export interface StepProgress {
  step: number;
  total: number;
  label: string;
  status: "running" | "done";
}

export interface AnalyzeStreamCallbacks {
  onProgress: (progress: StepProgress) => void;
  onResult: (result: AnalysisResult) => void;
  onError: (message: string) => void;
}

export async function analyzeQueryStream(
  statementId: string,
  callbacks: AnalyzeStreamCallbacks,
): Promise<void> {
  const url = `${BASE}/analyze/${encodeURIComponent(statementId)}/stream`;
  const res = await fetch(url);

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    callbacks.onError(body.detail || `Request failed: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("Streaming not supported");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const chunk of lines) {
        const dataLine = chunk.trim();
        if (!dataLine.startsWith("data: ")) continue;
        const jsonStr = dataLine.slice(6);

        try {
          const msg = JSON.parse(jsonStr);

          if (msg.event === "error") {
            callbacks.onError(msg.detail || "Analysis failed");
            completed = true;
            return;
          }

          if (msg.event === "result" && isAnalysisResult(msg.data)) {
            callbacks.onResult(msg.data);
            completed = true;
            return;
          }

          if (typeof msg.step === "number" && typeof msg.label === "string") {
            callbacks.onProgress(msg as StepProgress);
          }
        } catch {
          // ignore malformed chunks
        }
      }
    }
  } finally {
    if (!completed) {
      callbacks.onError("Analysis ended unexpectedly");
    }
  }
}

export function rewriteQuery(statementId: string, customInstruction?: string): Promise<AIRewriteResult> {
  const body = customInstruction ? { custom_instruction: customInstruction } : undefined;
  return request<AIRewriteResult>(`${BASE}/rewrite/${encodeURIComponent(statementId)}`, {
    method: "POST",
    ...(body && {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  });
}

export function benchmarkQueries(
  originalSql: string,
  suggestedSql: string,
  warehouseId?: string,
): Promise<BenchmarkResult> {
  return request<BenchmarkResult>(`${BASE}/benchmark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      original_sql: originalSql,
      suggested_sql: suggestedSql,
      warehouse_id: warehouseId ?? null,
    }),
  });
}

function isAnalysisResult(data: unknown): data is AnalysisResult {
  return (
    typeof data === "object" &&
    data !== null &&
    "query_metrics" in data &&
    typeof (data as Record<string, unknown>).query_metrics === "object"
  );
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// v2: Batch scan
// ---------------------------------------------------------------------------

export interface ScanStreamCallbacks {
  onProgress: (progress: StepProgress) => void;
  onResult: (result: ScanResult) => void;
  onError: (message: string) => void;
}

export async function scanQueryStream(
  filters: ScanFilter,
  callbacks: ScanStreamCallbacks,
): Promise<void> {
  const url = `${BASE}/scan/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    callbacks.onError(body.detail || `Request failed: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("Streaming not supported");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const chunk of lines) {
        const dataLine = chunk.trim();
        if (!dataLine.startsWith("data: ")) continue;
        const jsonStr = dataLine.slice(6);
        try {
          const msg = JSON.parse(jsonStr);
          if (msg.event === "error") {
            callbacks.onError(msg.detail || "Scan failed");
            completed = true;
            return;
          }
          if (msg.event === "result") {
            callbacks.onResult(msg.data);
            completed = true;
            return;
          }
          if (typeof msg.step === "number" && typeof msg.label === "string") {
            callbacks.onProgress(msg as StepProgress);
          }
        } catch {
          // ignore malformed chunks
        }
      }
    }
  } finally {
    if (!completed) {
      callbacks.onError("Scan ended unexpectedly");
    }
  }
}

// ---------------------------------------------------------------------------
// v2: Raw SQL analysis
// ---------------------------------------------------------------------------

export function analyzeSql(sql: string): Promise<RawSQLResult> {
  return request<RawSQLResult>(`${BASE}/analyze/sql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
}

// ---------------------------------------------------------------------------
// v2: History & trending
// ---------------------------------------------------------------------------

export function getHistory(statementId?: string, limit?: number): Promise<AnalysisRecord[]> {
  const params = new URLSearchParams();
  if (statementId) params.set("statement_id", statementId);
  if (limit) params.set("limit", String(limit));
  return request<AnalysisRecord[]>(`${BASE}/history?${params}`);
}

export function getTrends(statementId?: string, limit?: number): Promise<TrendPoint[]> {
  const params = new URLSearchParams();
  if (statementId) params.set("statement_id", statementId);
  if (limit) params.set("limit", String(limit));
  return request<TrendPoint[]>(`${BASE}/trends?${params}`);
}

// ---------------------------------------------------------------------------
// v2: Annotations
// ---------------------------------------------------------------------------

export function createAnnotation(
  statementId: string,
  recommendationTitle: string,
  status: AnnotationStatus,
  note?: string,
): Promise<RecommendationAnnotation> {
  return request<RecommendationAnnotation>(`${BASE}/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      statement_id: statementId,
      recommendation_title: recommendationTitle,
      status,
      note,
    }),
  });
}

export function getAnnotations(statementId: string): Promise<RecommendationAnnotation[]> {
  return request<RecommendationAnnotation[]>(`${BASE}/annotations/${encodeURIComponent(statementId)}`);
}

export function deleteAnnotation(annotationId: string): Promise<void> {
  return request(`${BASE}/annotations/${encodeURIComponent(annotationId)}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// v2: Table health
// ---------------------------------------------------------------------------

export function scanTables(filters: TableHealthScanFilter): Promise<TableHealthResult> {
  return request<TableHealthResult>(`${BASE}/tables/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });
}

// ---------------------------------------------------------------------------
// v2: Warehouse fleet
// ---------------------------------------------------------------------------

export function getWarehouses(): Promise<WarehouseFleetResult> {
  return request<WarehouseFleetResult>(`${BASE}/warehouses`);
}

// ---------------------------------------------------------------------------
// v2: Export
// ---------------------------------------------------------------------------

export async function exportAnalysis(statementId: string, format: string): Promise<Blob> {
  const res = await fetch(`${BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ statement_id: statementId, format }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Export failed: ${res.status}`);
  }
  return res.blob();
}
