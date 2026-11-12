import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
export const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: d });
export const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${fmt(v, 1)}%`;
export const money = (v: number | null | undefined) =>
  v == null ? "—" : `₹${fmt(v, 0)}`;
export const localTime = (s: string) =>
  new Date(s).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "short",
  });
export type Filters = {
  city: string;
  center: string;
  start: string;
  end: string;
};
export const queryString = (filters: Record<string, unknown>) => {
  const p = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) p.set(k, String(v));
  });
  return p.toString();
};
export async function api<T = any>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch("/api/v1/" + path, options);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return response.json();
}
export const download = (
  dataset: string,
  filters: Record<string, unknown> = {},
) => `/api/v1/exports/${dataset}?${queryString(filters)}`;
