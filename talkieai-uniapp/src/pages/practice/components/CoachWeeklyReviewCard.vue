<template>
  <view class="weekly-review-card">
    <view class="weekly-review-head">
      <text class="weekly-review-title">Weekly Review</text>
      <text v-if="staleHintText" class="weekly-review-stale">{{ staleHintText }}</text>
    </view>

    <view class="weekly-review-content">
      <view v-if="loading" class="weekly-state weekly-loading">
        <view class="weekly-kpi-row">
          <view v-for="i in 3" :key="'loading-kpi-' + i" class="loading-kpi" />
        </view>
        <view class="loading-chart">
          <view v-for="i in 7" :key="'loading-bar-' + i" class="loading-col">
            <view class="loading-track">
              <view class="loading-fill" :style="{ height: loadingHeights[i - 1] }" />
            </view>
          </view>
        </view>
      </view>

      <view v-else-if="isEmpty" class="weekly-state weekly-empty">
        <text class="empty-title">No plans this week yet</text>
        <text class="empty-body">Start or refine goals in chat to unlock the weekly review.</text>
      </view>

      <view v-else class="weekly-state weekly-ready">
        <view class="weekly-kpi-row">
          <view class="kpi-pill">
            <text class="kpi-label">Week</text>
            <text class="kpi-value">{{ weekRangeText }}</text>
          </view>
          <view class="kpi-pill">
            <text class="kpi-label">Done</text>
            <text class="kpi-value">{{ doneText }}</text>
          </view>
          <view class="kpi-pill">
            <text class="kpi-label">Rate</text>
            <text class="kpi-value">{{ completionRateText }}</text>
          </view>
        </view>

        <text v-if="deltaText" class="weekly-delta">{{ deltaText }} vs last week</text>

        <view class="weekday-chart" aria-label="Mon to Sun completion distribution">
          <view v-for="bar in bars" :key="'bar-' + bar.key" class="weekday-col">
            <view class="weekday-track">
              <view class="weekday-fill" :style="{ height: bar.height + '%' }" />
            </view>
            <text class="weekday-count">{{ bar.count }}</text>
            <text class="weekday-label">{{ bar.label }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { formatPercent, formatSignedPercentDelta, maxSeriesValue } from "./coachReviewFormatters";

type WeeklyDistribution = {
  day?: string;
  label?: string;
  count?: number;
};

type WeeklyReviewPayload = {
  week_range?: string;
  planned_count?: number;
  completed_count?: number;
  completion_rate?: number;
  vs_last_week_rate?: number;
  weekday_distribution?: WeeklyDistribution[];
};

const props = withDefaults(
  defineProps<{
    review?: WeeklyReviewPayload | null;
    loading?: boolean;
    stale?: boolean;
    lastUpdatedAt?: string;
  }>(),
  {
    review: null,
    loading: false,
    stale: false,
    lastUpdatedAt: "",
  }
);

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const loadingHeights = ["36%", "62%", "48%", "74%", "57%", "41%", "66%"];

function normalizeDayKey(value: unknown): string {
  if (typeof value !== "string") return "";
  const key = value.trim().slice(0, 3).toLowerCase();
  return DAY_KEYS.includes(key) ? key : "";
}

const staleHintText = computed(() => {
  if (!props.stale) return "";
  if (!props.lastUpdatedAt) return "Data may be outdated";
  return `Data may be outdated | ${props.lastUpdatedAt}`;
});

const plannedCount = computed(() => Number(props.review?.planned_count ?? 0));
const completedCount = computed(() => Number(props.review?.completed_count ?? 0));

const isEmpty = computed(() => plannedCount.value <= 0);
const weekRangeText = computed(() => props.review?.week_range || "--");
const doneText = computed(() => `${completedCount.value} / ${plannedCount.value}`);
const completionRateText = computed(() => formatPercent(props.review?.completion_rate));
const deltaText = computed(() => formatSignedPercentDelta(props.review?.vs_last_week_rate));

const bars = computed(() => {
  const distribution = Array.isArray(props.review?.weekday_distribution)
    ? props.review?.weekday_distribution
    : [];
  const byDay: Record<string, number> = {};
  distribution.forEach((item) => {
    const key = normalizeDayKey(item?.day || item?.label);
    if (!key) return;
    const count = Number(item?.count ?? 0);
    byDay[key] = Number.isFinite(count) && count >= 0 ? count : 0;
  });
  const counts = DAY_KEYS.map((key) => byDay[key] ?? 0);
  const maxValue = maxSeriesValue(counts);
  return DAY_KEYS.map((key, index) => {
    const count = counts[index];
    const height = Math.round((count / maxValue) * 100);
    return {
      key,
      label: DAY_LABELS[index],
      count,
      height: Number.isFinite(height) ? height : 0,
    };
  });
});
</script>

<style scoped lang="scss">
@import "@/less/coach-purple.scss";

.weekly-review-card {
  background: rgba(255, 255, 255, 0.94);
  border: 1rpx solid rgba(124, 92, 191, 0.2);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 6rpx 22rpx rgba(93, 61, 158, 0.08);
}

.weekly-review-head {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 16rpx;
}

.weekly-review-title {
  font-size: 30rpx;
  font-weight: 600;
  color: $coach-purple-800;
}

.weekly-review-stale {
  font-size: 22rpx;
  color: $coach-text-muted;
}

.weekly-review-content {
  min-height: 280rpx;
}

.weekly-state {
  min-height: 280rpx;
}

.weekly-kpi-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.kpi-pill {
  flex: 1;
  min-width: 0;
  padding: 14rpx 16rpx;
  border-radius: 14rpx;
  background: $coach-purple-50;
}

.kpi-label {
  display: block;
  font-size: 20rpx;
  color: $coach-text-muted;
}

.kpi-value {
  display: block;
  margin-top: 6rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: $coach-purple-900;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.weekly-delta {
  display: block;
  margin-bottom: 14rpx;
  font-size: 22rpx;
  color: $coach-purple-700;
}

.weekday-chart {
  display: flex;
  align-items: flex-end;
  gap: 10rpx;
  min-height: 170rpx;
}

.weekday-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.weekday-track {
  width: 100%;
  height: 110rpx;
  border-radius: 999rpx;
  background: rgba(124, 92, 191, 0.14);
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.weekday-fill {
  width: 100%;
  min-height: 8rpx;
  background: linear-gradient(180deg, $coach-purple-400 0%, $coach-purple-600 100%);
}

.weekday-count {
  margin-top: 8rpx;
  font-size: 20rpx;
  color: $coach-purple-800;
}

.weekday-label {
  margin-top: 4rpx;
  font-size: 20rpx;
  color: $coach-text-muted;
}

.weekly-empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 8rpx 4rpx;
}

.empty-title {
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-800;
  margin-bottom: 10rpx;
}

.empty-body {
  font-size: 24rpx;
  line-height: 1.5;
  color: $coach-text-body;
}

.weekly-loading {
  display: flex;
  flex-direction: column;
}

.loading-kpi {
  flex: 1;
  height: 82rpx;
  border-radius: 14rpx;
  background: linear-gradient(90deg, rgba(124, 92, 191, 0.09) 0%, rgba(124, 92, 191, 0.18) 50%, rgba(124, 92, 191, 0.09) 100%);
}

.loading-chart {
  display: flex;
  align-items: flex-end;
  gap: 10rpx;
  min-height: 170rpx;
}

.loading-col {
  flex: 1;
}

.loading-track {
  width: 100%;
  height: 110rpx;
  border-radius: 999rpx;
  background: rgba(124, 92, 191, 0.12);
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.loading-fill {
  width: 100%;
  min-height: 8rpx;
  background: rgba(124, 92, 191, 0.32);
}
</style>

