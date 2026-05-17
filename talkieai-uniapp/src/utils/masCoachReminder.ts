/** 用于预约到点后避免重复自动跳转聊天 */
export const MAS_COACH_LAST_TRIGGERED_AT_KEY = "mas_coach_last_triggered_at";

/**
 * 同一轮 OA 预约触发应只消费一次：仅用 triggered_at 做去重（避免 next_review_time 在响应里时有时无导致键变化）。
 */
export function scheduleTriggerDedupeKey(triggeredAt: string | null | undefined): string {
  if (triggeredAt == null || triggeredAt === "") return "";
  const raw = String(triggeredAt).trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (!isNaN(d.getTime())) return d.toISOString();
  return raw;
}

export function unwrapNextReviewPayload(res: any): Record<string, any> {
  const raw = res?.data;
  if (
    raw &&
    typeof raw === "object" &&
    raw.next_review_time === undefined &&
    raw.data
  ) {
    return raw.data;
  }
  return raw || {};
}

export function formatNextAppointmentText(nextIso: string | null | undefined): string {
  if (!nextIso) return "";
  const d = new Date(nextIso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
