import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import evidence from "../../../docs/evidence.json";
import { Predictive } from "./Models";

vi.mock("../App", () => ({
  useData: (path: string) => ({
    isPending: false,
    error: null,
    data:
      path === "models/performance"
        ? evidence.model
        : path === "predictions/high-risk"
          ? { rows: [], total: 0 }
          : { sufficient: false, warning: "No history in this test" },
  }),
}));
vi.mock("../components/common", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("../components/common")>();
  return { ...original, Bars: () => null, ForecastChart: () => null };
});
afterEach(() => vi.unstubAllGlobals());

it("allows the default dispatch inputs through browser validation and submits a prediction", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({
        delay_probability: 0.42,
        risk_level: "MEDIUM",
        model_version: "test-model",
        prediction_timestamp: "2026-11-12T00:00:00Z",
        explanation: "Validation estimate",
      }),
    });
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <Predictive
        filters={{ city: "", center: "", start: "", end: "" }}
        meta={{
          centers: [{ fulfillment_center_id: "FC1", center_name: "Demo Hub" }],
          partners: [
            { delivery_partner_id: "LP1", partner_name: "Fictional Partner" },
          ],
          zones: [
            { zone_id: "Z000", zone_code: "SYN-00000", city: "Bengaluru" },
          ],
        }}
      />
    </QueryClientProvider>,
  );
  const form = screen
    .getByRole("button", { name: "Estimate delay risk" })
    .closest("form")!;
  expect(form).toBeValid();
  fireEvent.submit(form);
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/predictions/delay",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(
    await screen.findByText("Estimated delay probability"),
  ).toBeInTheDocument();
});
