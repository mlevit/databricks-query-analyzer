import { describe, expect, it } from "vitest";
import type {
  AnalysisResult,
  Recommendation,
  ScanFilter,
  ScanResult,
  QuerySummary,
  WorkloadPattern,
  HealthScore,
  TrendPoint,
  AnalysisRecord,
  RecommendationAnnotation,
  RawSQLResult,
} from "../types";

describe("Type contracts", () => {
  it("creates a valid Recommendation", () => {
    const rec: Recommendation = {
      severity: "warning",
      category: "query",
      title: "Test",
      description: "Test description",
      impact: 5,
    };
    expect(rec.severity).toBe("warning");
    expect(rec.impact).toBe(5);
  });

  it("creates a valid ScanFilter", () => {
    const filter: ScanFilter = {
      warehouse_id: "wh-123",
      max_results: 20,
    };
    expect(filter.warehouse_id).toBe("wh-123");
  });

  it("creates a valid QuerySummary", () => {
    const qs: QuerySummary = {
      statement_id: "abc",
      statement_text: "SELECT 1",
      execution_status: "FINISHED",
      total_duration_ms: 1000,
      user_name: "user@test.com",
      warehouse_id: "wh-123",
      health_score: 85,
      recommendation_count: 3,
      critical_count: 0,
      warning_count: 2,
      info_count: 1,
      top_recommendations: ["SELECT * used"],
    };
    expect(qs.health_score).toBe(85);
  });

  it("creates a valid ScanResult", () => {
    const result: ScanResult = {
      filters: {},
      queries: [],
      patterns: [],
      total_queries_scanned: 0,
      total_duration_ms: 0,
      scanned_at: "2024-01-01T00:00:00Z",
    };
    expect(result.total_queries_scanned).toBe(0);
  });

  it("creates a valid TrendPoint", () => {
    const tp: TrendPoint = {
      analyzed_at: "2024-01-01",
      health_score: 85,
      recommendation_count: 3,
    };
    expect(tp.health_score).toBe(85);
  });

  it("creates a valid RawSQLResult", () => {
    const result: RawSQLResult = {
      recommendations: [],
      health_score: 100,
      tables_referenced: ["db.schema.table"],
    };
    expect(result.health_score).toBe(100);
  });
});
