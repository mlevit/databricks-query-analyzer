import { describe, expect, it } from "vitest";
import { humanBytes, formatNumber } from "../utils";

describe("humanBytes", () => {
  it("returns 0 B for null", () => {
    expect(humanBytes(null)).toBe("0 B");
  });

  it("returns 0 B for 0", () => {
    expect(humanBytes(0)).toBe("0 B");
  });

  it("formats bytes", () => {
    expect(humanBytes(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(humanBytes(2048)).toBe("2.0 KB");
  });

  it("formats megabytes", () => {
    expect(humanBytes(1024 * 1024 * 5)).toBe("5.0 MB");
  });

  it("formats gigabytes", () => {
    expect(humanBytes(1024 * 1024 * 1024 * 2.5)).toBe("2.5 GB");
  });
});

describe("formatNumber", () => {
  it("returns N/A for null", () => {
    expect(formatNumber(null)).toBe("N/A");
  });

  it("formats numbers with locale string", () => {
    const result = formatNumber(1234567);
    expect(result).toContain("1");
    expect(result).toContain("234");
  });
});
