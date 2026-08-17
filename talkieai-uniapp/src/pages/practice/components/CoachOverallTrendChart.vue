<template>
  <view class="overall-trend-card" role="img" :aria-label="chartAriaLabel">
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

    <view v-if="chartType === 'bar'" class="overall-trend-chart">
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

    <view v-else class="overall-trend-line-chart">
      <view class="overall-trend-line-canvas">
        <svg
          class="overall-trend-svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polygon
            v-if="chartType === 'area' && hasTrend"
            :points="areaPoints"
            class="overall-trend-area"
          />
          <polyline
            v-if="hasTrend"
            :points="linePoints"
            class="overall-trend-line"
          />
        </svg>

        <view
          v-for="point in lineCoordinates"
          :key="point.key"
          class="overall-trend-point"
          :style="{ left: point.x + '%', bottom: point.bottom + '%' }"
        >
          <text class="overall-trend-point-value">{{ point.displayValue }}</text>
          <view class="overall-trend-point-dot" />
        </view>
      </view>

      <view class="overall-trend-line-labels">
        <text
          v-for="point in lineCoordinates"
          :key="point.key + '-label'"
          class="overall-trend-label"
        >{{ point.label }}</text>
      </view>
      <text v-if="!hasTrend" class="overall-trend-hint">
        More weekly reviews are required to establish a trend.
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { maxSeriesValue } from "./coachReviewFormatters";

type ChartType = "bar" | "line" | "area";

type TrendPoint = {
  label: string;
  primary: number;
  secondary?: number;
};

const props = withDefaults(
  defineProps<{
    title: string;
    points?: TrendPoint[];
    chartType?: ChartType;
    yMax?: number;
    valueSuffix?: string;
    hasSecondary?: boolean;
    primaryLegend?: string;
    secondaryLegend?: string;
  }>(),
  {
    points: () => [],
    chartType: "bar",
    yMax: 0,
    valueSuffix: "",
    hasSecondary: false,
    primaryLegend: "",
    secondaryLegend: "",
  }
);

const showLegend = computed(
  () => props.hasSecondary && !!props.primaryLegend && !!props.secondaryLegend
);

const safePoints = computed(() => (Array.isArray(props.points) ? props.points : []));

const seriesMax = computed(() => {
  if (Number(props.yMax) > 0) return Number(props.yMax);
  return maxSeriesValue(safePoints.value.map((item) => Number(item?.primary ?? 0)));
});

const columns = computed(() => {
  const values = safePoints.value.flatMap((item) => {
    const first = Number(item?.primary ?? 0);
    const second = Number(item?.secondary ?? 0);
    return props.hasSecondary ? [first, second] : [first];
  });
  const maxValue = maxSeriesValue(values);

  return safePoints.value.map((item, index) => {
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

const lineCoordinates = computed(() => {
  const maxValue = seriesMax.value || 1;
  const lastIndex = safePoints.value.length - 1;

  return safePoints.value.map((item, index) => {
    const value = Math.max(0, Number(item?.primary ?? 0));
    const ratio = Math.min(1, value / maxValue);
    const x = lastIndex <= 0 ? 50 : 4 + (index / lastIndex) * 92;
    const y = 94 - ratio * 84;

    return {
      key: `${item?.label || "-"}-${index}`,
      label: item?.label || "-",
      x: Number(x.toFixed(2)),
      y: Number(y.toFixed(2)),
      bottom: Number((100 - y).toFixed(2)),
      displayValue: `${value}${props.valueSuffix}`,
    };
  });
});

const hasTrend = computed(() => lineCoordinates.value.length > 1);
const linePoints = computed(() =>
  lineCoordinates.value.map((point) => `${point.x},${point.y}`).join(" ")
);
const areaPoints = computed(() => {
  if (!hasTrend.value) return "";
  const first = lineCoordinates.value[0];
  const last = lineCoordinates.value[lineCoordinates.value.length - 1];
  return `${first.x},94 ${linePoints.value} ${last.x},94`;
});

const chartAriaLabel = computed(() => {
  const values = safePoints.value.map((point) => {
    const primary = `${Math.max(0, Number(point?.primary ?? 0))}${props.valueSuffix}`;
    if (!props.hasSecondary) return `${point?.label || "-"}: ${primary}`;
    return `${point?.label || "-"}: ${props.primaryLegend} ${primary}, ${props.secondaryLegend} ${Math.max(0, Number(point?.secondary ?? 0))}${props.valueSuffix}`;
  });
  return `${props.title}. ${values.join("; ")}`;
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

.overall-trend-line-chart {
  margin-top: 12rpx;
}

.overall-trend-line-canvas {
  position: relative;
  height: 132rpx;
  border-radius: 12rpx;
  background: repeating-linear-gradient(
    to bottom,
    rgba(124, 92, 191, 0.08) 0,
    rgba(124, 92, 191, 0.08) 1rpx,
    transparent 1rpx,
    transparent 33rpx
  );
}

.overall-trend-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.overall-trend-area {
  fill: rgba(124, 92, 191, 0.16);
}

.overall-trend-line {
  fill: none;
  stroke: $coach-purple-600;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

.overall-trend-point {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  transform: translate(-50%, 50%);
}

.overall-trend-point-value {
  margin-bottom: 4rpx;
  padding: 1rpx 5rpx;
  border-radius: 6rpx;
  background: rgba(255, 255, 255, 0.9);
  font-size: 18rpx;
  line-height: 1.2;
  color: $coach-purple-800;
}

.overall-trend-point-dot {
  width: 12rpx;
  height: 12rpx;
  border: 3rpx solid $coach-purple-600;
  border-radius: 50%;
  background: #fff;
  box-sizing: border-box;
}

.overall-trend-line-labels {
  display: flex;
  justify-content: space-between;
  gap: 6rpx;
  margin-top: 6rpx;
}

.overall-trend-line-labels .overall-trend-label {
  flex: 1;
  text-align: center;
}

.overall-trend-hint {
  display: block;
  margin-top: 8rpx;
  font-size: 20rpx;
  line-height: 1.4;
  color: $coach-text-muted;
  text-align: center;
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
