export type ReviewWindow = "5" | "10" | "all";

export const REVIEW_WINDOW_OPTIONS: Array<{ label: string; value: ReviewWindow }> = [
  { label: "5 weeks", value: "5" },
  { label: "10 weeks", value: "10" },
  { label: "Overall", value: "all" },
];

export function normalizeReviewWindow(window: unknown): ReviewWindow {
  if (window === "5" || window === "10" || window === "all") {
    return window;
  }
  return "5";
}

export function formatReviewTimestamp(value: string | number | Date | null | undefined): string {
  if (value == null || value === "") return "Never";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "Never";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function normalizePercentValue(value: number | string | null | undefined): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

export function formatPercent(value: number | string | null | undefined, digits = 0): string {
  const normalized = normalizePercentValue(value);
  if (normalized == null) return "--";
  return `${normalized.toFixed(digits)}%`;
}

export function formatSignedPercentDelta(value: number | string | null | undefined, digits = 1): string {
  const normalized = normalizePercentValue(value);
  if (normalized == null) return "--";
  if (normalized === 0) return "0%";
  const sign = normalized > 0 ? "+" : "";
  return `${sign}${normalized.toFixed(digits)}%`;
}

export function maxSeriesValue(series: unknown): number {
  if (!Array.isArray(series) || series.length === 0) return 0;

  let max = 0;
  for (const item of series) {
    const raw =
      typeof item === "number"
        ? item
        : item && typeof item === "object" && "value" in item
          ? Number((item as { value: unknown }).value)
          : Number.NaN;
    if (Number.isFinite(raw)) {
      max = Math.max(max, raw);
    }
  }
  return max;
}
