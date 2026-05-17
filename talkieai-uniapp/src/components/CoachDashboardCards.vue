<template>
  <view
    class="coach-dashboard-cards"
    :class="{ compact: compact && !merged, merged: merged, 'is-loading': loading }"
  >
    <!-- 聊天顶栏：单卡摘要（原 Weekly / Next / Plan 合一） -->
    <view v-if="merged" class="card card-merged card-merged-simple">
      <view class="merged-tap" @tap="emit('next-tap')">
        <view class="merged-tap-top">
          <text class="merged-line merged-line-week">{{ weeklyLine }}</text>
          <text class="merged-chevron">›</text>
        </view>
        <text class="merged-line merged-line-strong">{{ nextWorkoutLine }}</text>
        <text class="merged-line merged-line-muted">{{ nextWorkoutDesc }}</text>
        <text class="merged-line merged-line-muted merged-line-plan">{{ planIcon }} {{ planName }} · {{ planDuration }} · {{ planSchedule }}</text>
      </view>
      <view class="plan-actions merged-actions">
        <view class="btn btn-secondary" @tap.stop="emit('modify')">Modify</view>
        <view class="btn btn-primary" @tap.stop="onMarkComplete">Mark Complete</view>
      </view>
    </view>

    <template v-else>
      <view class="top-row">
        <view class="card card-beige weekly-card">
          <text class="card-title">Weekly Progress</text>
          <view
            v-if="weeklyDotCount > 0"
            class="progress-dots"
            :style="{
              gap: weeklyDotsVisual.gap + 'rpx',
            }"
          >
            <view
              v-for="i in weeklyDotCount"
              :key="'wd-' + i"
              :class="['progress-dot', i <= weeklyFilledCount ? 'done' : 'pending']"
              :style="{
                width: weeklyDotsVisual.size + 'rpx',
                height: weeklyDotsVisual.size + 'rpx',
              }"
            />
          </view>
          <text class="sub-line">{{ weeklyLine }}</text>
        </view>
        <view class="card card-beige next-workout-card" @tap="emit('next-tap')">
          <view class="card-title-row">
            <text class="card-title">Next Workout</text>
            <text class="arrow-icon">›</text>
          </view>
          <text class="workout-time">{{ nextWorkoutLine }}</text>
          <text class="workout-desc">{{ nextWorkoutDesc }}</text>
        </view>
      </view>

      <view class="card card-purple plan-card">
        <view class="plan-header">
          <text class="plan-name">{{ planName }}</text>
          <view class="plan-badge"><text class="plan-badge-text">Plan</text></view>
        </view>
        <view class="plan-details">
          <view class="plan-icon-wrap">
            <text class="plan-icon">{{ planIcon }}</text>
          </view>
          <view class="plan-meta">
            <view class="meta-row">
              <text class="meta-icon">🕐</text>
              <text class="meta-text">{{ planDuration }}</text>
            </view>
            <view class="meta-row">
              <text class="meta-icon">📅</text>
              <text class="meta-text">{{ planSchedule }}</text>
            </view>
          </view>
        </view>
        <view class="plan-actions">
          <view class="btn btn-secondary" @tap.stop="emit('modify')">Modify</view>
          <view class="btn btn-primary" @tap.stop="onMarkComplete">Mark Complete</view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    dashboard: Record<string, any> | null;
    loading?: boolean;
    /** 纵向堆叠三卡（非 merged 时） */
    compact?: boolean;
    /** 聊天顶栏：三卡合一 */
    merged?: boolean;
  }>(),
  { loading: false, compact: false, merged: false }
);

const emit = defineEmits<{
  (e: "mark-complete", goalIndex: number): void;
  (e: "modify"): void;
  (e: "next-tap"): void;
}>();

/** 圆点过多时压缩显示，避免挤爆一行；总量大于此时用比例映射到显示格数 */
const WEEKLY_DOTS_DISPLAY_MAX = 48;

const weeklyDotCount = computed(() => {
  if (props.loading) return 0;
  const w = props.dashboard?.weekly_progress;
  const t = Number(w?.total);
  if (!Number.isFinite(t) || t <= 0) return 0;
  return Math.min(Math.floor(t), WEEKLY_DOTS_DISPLAY_MAX);
});

/** 与圆点列一一对应：完成了几个就有几个实心（总量超上限时按比例） */
const weeklyFilledCount = computed(() => {
  if (props.loading) return 0;
  const w = props.dashboard?.weekly_progress;
  const t = Number(w?.total);
  const c = Number(w?.completed);
  if (!Number.isFinite(t) || t <= 0) return 0;
  const done = Number.isFinite(c) ? Math.max(0, Math.floor(c)) : 0;
  const shown = weeklyDotCount.value;
  if (shown <= 0) return 0;
  if (t <= WEEKLY_DOTS_DISPLAY_MAX) {
    return Math.min(done, t, shown);
  }
  return Math.min(shown, Math.round((done / t) * shown));
});

/** 圆点大小与间距随「当前显示的圆点个数」变化：与下方 X / Y 总量一致，越多越小以便排开 */
const weeklyDotsVisual = computed(() => {
  const n = weeklyDotCount.value;
  if (n <= 0) return { size: 20, gap: 12 };
  const size = Math.max(8, Math.min(28, Math.floor(280 / n)));
  const gap = Math.max(3, Math.min(12, Math.floor(size * 0.4)));
  return { size, gap };
});

const weeklyLine = computed(() => {
  if (props.loading) return "Loading…";
  const w = props.dashboard?.weekly_progress;
  if (!w?.total) return "No weekly goals yet";
  return `${w.completed} / ${w.total} · ${w.rate ?? 0}%`;
});

const nextWorkoutLine = computed(() => {
  if (props.loading) return "Loading…";
  const nw = props.dashboard?.next_workout;
  if (!nw?.summary) return "No workout scheduled yet";
  return nw.scheduled_display || "This week";
});

const nextWorkoutDesc = computed(() => {
  if (props.loading) return "";
  const nw = props.dashboard?.next_workout;
  if (!nw?.summary) {
    return "Add any goal or plan in chat — SMART format optional.";
  }
  const dur = nw.duration_min ? `${nw.duration_min} min` : "";
  const ty = nw.activity_type || "";
  return [dur, ty].filter(Boolean).join(" · ") || nw.summary.slice(0, 80);
});

const planName = computed(() => {
  if (props.loading) return "Loading…";
  const nw = props.dashboard?.next_workout;
  if (!nw?.summary) return "No plan yet";
  return nw.summary.length > 40 ? nw.summary.slice(0, 40) + "…" : nw.summary;
});

const planDuration = computed(() => {
  if (props.loading) return "—";
  const nw = props.dashboard?.next_workout;
  if (nw?.duration_min) return `${nw.duration_min} min`;
  return "—";
});

const planSchedule = computed(() => {
  if (props.loading) return "—";
  const nw = props.dashboard?.next_workout;
  return nw?.scheduled_display || "—";
});

const planIcon = computed(() => {
  const t = (props.dashboard?.next_workout?.activity_type || "").toLowerCase();
  const map: Record<string, string> = {
    walk: "🚶",
    run: "🏃",
    swim: "🏊",
    stretch: "🧘",
    sport: "🎾",
    exercise: "💪",
    activity: "🚴",
  };
  return map[t] || "🚴";
});

function onMarkComplete() {
  const idx = props.dashboard?.next_workout?.goal_index;
  if (typeof idx === "number") {
    emit("mark-complete", idx);
    return;
  }
  uni.showToast({ title: "No goal to mark", icon: "none" });
}
</script>

<style lang="scss" scoped>
@import "@/less/coach-purple.scss";

.coach-dashboard-cards.compact {
  padding-bottom: 16rpx;
  .top-row {
    flex-direction: column;
  }
  .card {
    margin-bottom: 12rpx;
  }
}

.coach-dashboard-cards.merged {
  padding-bottom: 8rpx;
}

.card-merged {
  background: $coach-purple-50;
  border: 1rpx solid rgba(124, 92, 191, 0.12);
}

.merged-tap {
  padding-bottom: 8rpx;
}

.merged-tap-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 6rpx;
}

.merged-chevron {
  flex-shrink: 0;
  font-size: 36rpx;
  color: $coach-purple-400;
  line-height: 1;
  margin-top: -4rpx;
}

.merged-line {
  display: block;
  font-size: 24rpx;
  color: $coach-text-body;
  line-height: 1.4;
}

.merged-line-week {
  flex: 1;
  min-width: 0;
  font-size: 24rpx;
  color: $coach-text-muted;
}

.merged-line-strong {
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-800;
  margin-top: 4rpx;
}

.merged-line-muted {
  font-size: 22rpx;
  color: $coach-text-body;
  margin-top: 4rpx;
}

.merged-line-plan {
  margin-top: 6rpx;
  font-size: 22rpx;
  color: $coach-text-muted;
}

.coach-dashboard-cards.is-loading {
  opacity: 0.92;
}

.dash-loading {
  padding: 24rpx;
  text-align: center;
  color: $coach-text-muted;
  font-size: 26rpx;
}

.top-row {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.card {
  border-radius: 24rpx;
  padding: 24rpx;
  box-sizing: border-box;
}

.card.card-merged-simple {
  padding: 20rpx 22rpx;
}

.card-beige {
  background: $coach-purple-50;
  border: 1rpx solid rgba(124, 92, 191, 0.12);
}

.card-purple {
  background: $coach-purple-100;
  border: 1rpx solid rgba(108, 92, 231, 0.1);
}

.weekly-card {
  flex: 1;
  min-width: 0;
}

.next-workout-card {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 26rpx;
  font-weight: 600;
  color: $coach-text-strong;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.arrow-icon {
  font-size: 36rpx;
  color: $coach-purple-400;
}

.progress-dots {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 16rpx;
  max-width: 100%;
}

.progress-dot {
  flex-shrink: 0;
  border-radius: 50%;
  box-sizing: border-box;
  background: $coach-purple-200;
}

.progress-dot.done {
  background: $coach-purple-500;
}

.sub-line {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  color: $coach-text-muted;
}

.workout-time {
  display: block;
  margin-top: 12rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-800;
}

.workout-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: $coach-text-body;
}

.plan-card {
  width: 100%;
}

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.plan-name {
  font-size: 30rpx;
  font-weight: 600;
  color: $coach-purple-950;
  flex: 1;
  padding-right: 16rpx;
}

.plan-badge {
  background: rgba(108, 92, 231, 0.18);
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
}

.plan-badge-text {
  font-size: 22rpx;
  color: $coach-accent;
}

.plan-details {
  display: flex;
  margin-top: 20rpx;
  gap: 20rpx;
}

.plan-icon-wrap {
  width: 100rpx;
  height: 100rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.65);
  border-radius: 20rpx;
  border: 1rpx solid rgba(124, 92, 191, 0.15);
}

.plan-icon {
  font-size: 56rpx;
}

.plan-meta {
  flex: 1;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.meta-text {
  font-size: 26rpx;
  color: $coach-text-body;
}

.plan-actions {
  display: flex;
  gap: 20rpx;
  margin-top: 24rpx;
}

.plan-actions.merged-actions {
  margin-top: 12rpx;
}

.btn {
  flex: 1;
  text-align: center;
  padding: 20rpx;
  border-radius: 16rpx;
  font-size: 26rpx;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.85);
  color: $coach-purple-700;
  border: 1rpx solid rgba(124, 92, 191, 0.35);
}

.btn-primary {
  background: $coach-purple-600;
  color: #fff;
  box-shadow: 0 4rpx 14rpx rgba(108, 92, 231, 0.28);
}
</style>
