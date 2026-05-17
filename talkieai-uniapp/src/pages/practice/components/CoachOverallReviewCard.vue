<template>
  <view class="overall-review-card">
    <view class="overall-review-head">
      <text class="overall-review-title">Overall Review</text>
      <text v-if="staleHintText" class="overall-review-stale">{{ staleHintText }}</text>
    </view>

    <view class="window-switch">
      <view
        v-for="item in REVIEW_WINDOW_OPTIONS"
        :key="item.value"
        class="window-pill"
        :class="{ active: item.value === activeWindow }"
        @tap="emit('window-change', item.value)"
      >
        <text class="window-pill-text">{{ item.label }}</text>
      </view>
    </view>

    <view v-if="loading" class="overall-state overall-loading">
      <view class="kpi-row">
        <view v-for="i in 3" :key="'overall-kpi-loading-' + i" class="kpi-pill loading-pill" />
      </view>
      <view class="loading-chart" />
      <view class="loading-chart" />
      <view class="loading-chart" />
    </view>

    <view v-else-if="isEmpty" class="overall-state overall-empty">
      <text class="empty-title">No historical data for this range</text>
      <text class="empty-body">Complete a few weekly goals to unlock cross-week trends.</text>
    </view>

    <view v-else class="overall-state overall-ready">
      <view class="kpi-row">
        <view class="kpi-pill">
          <text class="kpi-label">Planned</text>
          <text class="kpi-value">{{ plannedTotal }}</text>
        </view>
        <view class="kpi-pill">
          <text class="kpi-label">Completed</text>
          <text class="kpi-value">{{ completedTotal }}</text>
        </view>
        <view class="kpi-pill">
          <text class="kpi-label">Rate</text>
          <text class="kpi-value">{{ completionRateText }}</text>
        </view>
      </view>

      <view class="trend-list">
        <CoachOverallTrendChart
          title="Completion Rate Trend"
          :points="completionRatePoints"
        />

        <CoachOverallTrendChart
          title="Plan vs Done Trend"
          :points="planVsDonePoints"
          :has-secondary="true"
          primary-legend="Planned"
          secondary-legend="Completed"
        />

        <CoachOverallTrendChart
          title="Cumulative Progress Trend"
          :points="cumulativeProgressPoints"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import CoachOverallTrendChart from "./CoachOverallTrendChart.vue";
import {
  REVIEW_WINDOW_OPTIONS,
  formatPercent,
  type ReviewWindow,
} from "./coachReviewFormatters";

type KpiPayload = {
  planned_total?: number;
  completed_total?: number;
  completion_rate?: number;
};

type TrendItem = {
  label?: string;
  week_label?: string;
  rate?: number;
  completion_rate?: number;
  planned?: number;
  planned_count?: number;
  completed?: number;
  completed_count?: number;
  completed_total?: number;
  cumulative_completed?: number;
};

type OverallReviewPayload = {
  kpi?: KpiPayload;
  completion_rate_trend?: TrendItem[];
  plan_vs_done_trend?: TrendItem[];
  cumulative_progress_trend?: TrendItem[];
};

const props = withDefaults(
  defineProps<{
    review?: OverallReviewPayload | null;
    loading?: boolean;
    activeWindow: ReviewWindow;
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

const emit = defineEmits<{
  (e: "window-change", value: ReviewWindow): void;
}>();

const staleHintText = computed(() => {
  if (!props.stale) return "";
  if (!props.lastUpdatedAt) return "Data may be outdated";
  return `Data may be outdated | ${props.lastUpdatedAt}`;
});

const completionRateTrend = computed(() =>
  Array.isArray(props.review?.completion_rate_trend) ? props.review?.completion_rate_trend : []
);
const planVsDoneTrend = computed(() =>
  Array.isArray(props.review?.plan_vs_done_trend) ? props.review?.plan_vs_done_trend : []
);
const cumulativeProgressTrend = computed(() =>
  Array.isArray(props.review?.cumulative_progress_trend) ? props.review?.cumulative_progress_trend : []
);

const isEmpty = computed(
  () =>
    completionRateTrend.value.length === 0 &&
    planVsDoneTrend.value.length === 0 &&
    cumulativeProgressTrend.value.length === 0
);

const plannedTotal = computed(() => Number(props.review?.kpi?.planned_total ?? 0));
const completedTotal = computed(() => Number(props.review?.kpi?.completed_total ?? 0));
const completionRateText = computed(() => formatPercent(props.review?.kpi?.completion_rate));

function pickLabel(item: TrendItem): string {
  return item?.label || item?.week_label || "-";
}

const completionRatePoints = computed(() =>
  completionRateTrend.value.map((item) => ({
    label: pickLabel(item),
    primary: Number(item?.rate ?? item?.completion_rate ?? 0),
  }))
);

const planVsDonePoints = computed(() =>
  planVsDoneTrend.value.map((item) => ({
    label: pickLabel(item),
    primary: Number(item?.planned ?? item?.planned_count ?? 0),
    secondary: Number(item?.completed ?? item?.completed_count ?? 0),
  }))
);

const cumulativeProgressPoints = computed(() =>
  cumulativeProgressTrend.value.map((item) => ({
    label: pickLabel(item),
    primary: Number(item?.completed_total ?? item?.cumulative_completed ?? 0),
  }))
);
</script>

<style scoped lang="scss">
@import "@/less/coach-purple.scss";

.overall-review-card {
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.96) 0%, rgba(246, 240, 255, 0.94) 100%);
  border: 1rpx solid rgba(124, 92, 191, 0.22);
  border-radius: 22rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 26rpx rgba(93, 61, 158, 0.1);
}

.overall-review-head {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 16rpx;
}

.overall-review-title {
  font-size: 30rpx;
  font-weight: 600;
  color: $coach-purple-900;
}

.overall-review-stale {
  font-size: 22rpx;
  color: $coach-text-muted;
}

.window-switch {
  display: flex;
  gap: 12rpx;
  margin-bottom: 18rpx;
  flex-wrap: wrap;
}

.window-pill {
  min-width: 132rpx;
  padding: 10rpx 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(124, 92, 191, 0.26);
  background: rgba(255, 255, 255, 0.86);
  display: flex;
  justify-content: center;
  align-items: center;
}

.window-pill.active {
  background: $coach-purple-600;
  border-color: $coach-purple-600;
  box-shadow: 0 6rpx 16rpx rgba(108, 92, 231, 0.25);
}

.window-pill-text {
  font-size: 22rpx;
  color: $coach-purple-800;
}

.window-pill.active .window-pill-text {
  color: #fff;
}

.overall-state {
  min-height: 300rpx;
}

.kpi-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.kpi-pill {
  flex: 1;
  min-width: 0;
  background: rgba(124, 92, 191, 0.08);
  border-radius: 14rpx;
  padding: 14rpx 16rpx;
}

.kpi-label {
  display: block;
  font-size: 20rpx;
  color: $coach-text-muted;
}

.kpi-value {
  display: block;
  margin-top: 6rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-900;
}

.trend-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.overall-empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 6rpx 4rpx;
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

.overall-loading {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.loading-pill {
  height: 78rpx;
  background: linear-gradient(90deg, rgba(124, 92, 191, 0.08) 0%, rgba(124, 92, 191, 0.18) 50%, rgba(124, 92, 191, 0.08) 100%);
}

.loading-chart {
  width: 100%;
  height: 160rpx;
  border-radius: 16rpx;
  background: linear-gradient(90deg, rgba(124, 92, 191, 0.06) 0%, rgba(124, 92, 191, 0.14) 50%, rgba(124, 92, 191, 0.06) 100%);
}
</style>
