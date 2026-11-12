import { afterEach, describe, expect, it, vi } from "vitest";
import { api, fmt, localTime, queryString } from "./lib";
afterEach(() => vi.restoreAllMocks());
describe("API and operational formatting", () => {
  it("preserves meaningful zero filters and encodes special characters", () => {
    expect(queryString({ city: "Delhi NCR", page: 0, empty: "" })).toBe(
      "city=Delhi+NCR&page=0",
    );
  });
  it("keeps missing values distinct from zero", () => {
    expect(fmt(null)).toBe("—");
    expect(fmt(0)).toBe("0");
  });
  it("displays operational timestamps in India time", () => {
    expect(localTime("2026-11-12T00:00:00Z")).toMatch(/5:30/);
  });
  it("surfaces backend validation failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Start date must not exceed end date" }),
      }),
    );
    await expect(api("overview")).rejects.toThrow("Start date");
  });
});
