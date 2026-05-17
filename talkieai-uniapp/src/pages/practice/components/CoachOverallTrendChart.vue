<template>
  <view class="overall-trend-card">
    <view class="overall-trend-head">
      <text class="overall-trend-title">{{ title }}</text>
      <view v-if="showLegend" class="overall-trend-legend">
        <view class="legend-item">
          <view class="legend-dot legend-dot-primary" />
          <text class="legend-text">{{ primaryLegend }}</text>
        </view>
        <view class="legend-item">
          <view class="legend-dot legend-dot-secondary" />
          <text class="legend-text">{{ secondaryLegend }}</text>
        </view>
      </view>
    </view>

    <view class="overall-trend-chart">
      <view v-for="item in columns" :key="item.key" class="overall-trend-col">
        <view class="overall-trend-track">
          <view class="overall-trend-bars">
            <view
              class="overall-trend-bar overall-trend-bar-primary"
              :style="{ height: item.primaryHeight + '%', minHeight: item.primaryValue > 0 ? '8rpx' : '0' }"
            />
            <view
              v-if="hasSecondary"
              class="overall-trend-bar overall-trend-bar-secondary"
              :style="{ height: item.secondaryHeight + '%', minHeight: item.secondaryValue > 0 ? '8rpx' : '0' }"
            />
          </view>
        </view>
        <text class="overall-trend-label">{{ item.label }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { maxSeriesValue } from "./coachReviewFormatters";

type TrendPoint = {
  label: string;
  primary: number;
  secondary?: number;
};

const props = withDefaults(
  defineProps<{
    title: string;
    points?: TrendPoint[];
    hasSecondary?: boolean;
    primaryLegend?: string;
    secondaryLegend?: string;
  }>(),
  {
    points: () => [],
    hasSecondary: false,
    primaryLegend: "",
    secondaryLegend: "",
  }
);

const showLegend = computed(
  () => props.hasSecondary && !!props.primaryLegend && !!props.secondaryLegend
);

const columns = computed(() => {
  const list = Array.isArray(props.points) ? props.points : [];
  const values = list.flatMap((item) => {
    const first = Number(item?.primary ?? 0);
    const second = Number(item?.secondary ?? 0);
    return props.hasSecondary ? [first, second] : [first];
  });
  const maxValue = maxSeriesValue(values);

  return list.map((item, index) => {
    const primary = Number(item?.primary ?? 0);
    const secondary = Number(item?.secondary ?? 0);
    const primaryHeight = Math.round((Math.max(0, primary) / maxValue) * 100);
    const secondaryHeight = Math.round((Math.max(0, secondary) / maxValue) * 100);

    return {
      key: `${item?.label || "-"}-${index}`,
      label: item?.label || "-",
      primaryValue: Math.max(0, primary),
      secondaryValue: Math.max(0, secondary),
      primaryHeight: Number.isFinite(primaryHeight) ? primaryHeight : 0,
      secondaryHeight: Number.isFinite(secondaryHeight) ? secondaryHeight : 0,
    };
  });
});
</script>

<style scoped lang="scss">
@import "@/less/coach-purple.scss";

.overall-trend-card {
  background: rgba(250, 247, 255, 0.85);
  border: 1rpx solid rgba(124, 92, 191, 0.14);
  border-radius: 16rpx;
  padding: 16rpx;
}

.overall-trend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.overall-trend-title {
  font-size: 24rpx;
  font-weight: 600;
  color: $coach-purple-800;
}

.overall-trend-legend {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.legend-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
}

.legend-dot-primary {
  background: $coach-purple-500;
}

.legend-dot-secondary {
  background: rgba(124, 92, 191, 0.3);
}

.legend-text {
  font-size: 20rpx;
  color: $coach-text-muted;
}

.overall-trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 10rpx;
  margin-top: 12rpx;
  min-height: 168rpx;
}

.overall-trend-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.overall-trend-track {
  width: 100%;
  height: 118rpx;
  border-radius: 999rpx;
  background: rgba(124, 92, 191, 0.1);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 8rpx;
  box-sizing: border-box;
}

.overall-trend-bars {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 8rpx;
}

.overall-trend-bar {
  flex: 1;
  border-radius: 999rpx 999rpx 0 0;
}

.overall-trend-bar-primary {
  background: linear-gradient(180deg, $coach-purple-400 0%, $coach-purple-600 100%);
}

.overall-trend-bar-secondary {
  background: rgba(124, 92, 191, 0.3);
}

.overall-trend-label {
  margin-top: 6rpx;
  font-size: 20rpx;
  color: $coach-text-muted;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
