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
            <view class="overall-trend-bar-wrap">
              <text class="overall-trend-bar-value">{{ item.primaryValue }}</text>
              <view
                class="overall-trend-bar overall-trend-bar-primary"
                :style="{ height: item.primaryHeight + '%', minHeight: item.primaryValue > 0 ? '8rpx' : '0' }"
              />
            </view>
            <view v-if="hasSecondary" class="overall-trend-bar-wrap">
              <text class="overall-trend-bar-value">{{ item.secondaryValue }}</text>
              <view
                class="overall-trend-bar overall-trend-bar-secondary"
                :style="{ height: item.secondaryHeight + '%', minHeight: item.secondaryValue > 0 ? '8rpx' : '0' }"
              />
            </view>
          </view>
        </view>
        <text class="overall-trend-label">{{ item.label }}</text>
      </view>
    </view>

    <view v-else class="overall-trend-line-chart">
      <view class="overall-trend-line-canvas">
        <canvas
          :id="canvasId"
          :canvas-id="canvasId"
          class="overall-trend-canvas"
          :hidpi="true"
          aria-hidden="true"
        />

        <view
          v-for="point in lineCoordinates"
          :key="point.key"
          class="overall-trend-point"
          :style="{ left: point.x + '%', top: point.y + '%' }"
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
import { computed, getCurrentInstance, nextTick, onMounted, watch } from "vue";
import { maxSeriesValue } from "./coachReviewFormatters";

type ChartType = "bar" | "line" | "area";

type TrendPoint = {
  label: string;
  primary: number;
  secondary?: number;
};

const HORIZONTAL_PADDING_PERCENT = 10;
const TOP_PADDING_PERCENT = 22;
const BASELINE_PERCENT = 84;
const BAR_MAX_HEIGHT_PERCENT = 72;

let chartInstanceSequence = 0;

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

const componentInstance = getCurrentInstance()?.proxy;
const canvasId = `coach-trend-canvas-${++chartInstanceSequence}`;

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
    const primaryHeight = Math.round(
      (Math.max(0, primary) / maxValue) * BAR_MAX_HEIGHT_PERCENT
    );
    const secondaryHeight = Math.round(
      (Math.max(0, secondary) / maxValue) * BAR_MAX_HEIGHT_PERCENT
    );

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
    const horizontalRange = 100 - HORIZONTAL_PADDING_PERCENT * 2;
    const x = lastIndex <= 0
      ? 50
      : HORIZONTAL_PADDING_PERCENT + (index / lastIndex) * horizontalRange;
    const y = BASELINE_PERCENT - ratio * (BASELINE_PERCENT - TOP_PADDING_PERCENT);

    return {
      key: `${item?.label || "-"}-${index}`,
      label: item?.label || "-",
      x: Number(x.toFixed(2)),
      y: Number(y.toFixed(2)),
      displayValue: `${value}${props.valueSuffix}`,
    };
  });
});

const hasTrend = computed(() => lineCoordinates.value.length > 1);

function drawTrendCanvas() {
  if (props.chartType === "bar") return;

  nextTick(() => {
    const query = uni.createSelectorQuery();
    if (componentInstance) query.in(componentInstance);

    query
      .select(`#${canvasId}`)
      .boundingClientRect((rect: any) => {
        const width = Number(rect?.width ?? 0);
        const height = Number(rect?.height ?? 0);
        if (width <= 0 || height <= 0) return;

        // DCloud CanvasContext API requires the component instance for a
        // canvas declared inside a custom component.
        const context = uni.createCanvasContext(canvasId, componentInstance);
        context.clearRect(0, 0, width, height);

        if (!hasTrend.value) {
          context.draw();
          return;
        }

        const points = lineCoordinates.value.map((point) => ({
          x: (point.x / 100) * width,
          y: (point.y / 100) * height,
        }));
        const baseline = (BASELINE_PERCENT / 100) * height;
        const first = points[0];
        const last = points[points.length - 1];

        if (props.chartType === "area") {
          context.beginPath();
          context.moveTo(first.x, baseline);
          points.forEach((point) => context.lineTo(point.x, point.y));
          context.lineTo(last.x, baseline);
          context.closePath();
          context.setFillStyle("rgba(124, 92, 191, 0.18)");
          context.fill();
        }

        context.beginPath();
        context.moveTo(first.x, first.y);
        points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
        context.setStrokeStyle("#6d4fb8");
        context.setLineWidth(2.4);
        context.setLineCap("round");
        context.setLineJoin("round");
        context.stroke();
        context.draw();
      })
      .exec();
  });
}

onMounted(drawTrendCanvas);
watch(
  [() => props.chartType, () => props.yMax, () => props.points],
  drawTrendCanvas,
  { deep: true, flush: "post" }
);

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
  overflow: hidden;
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
  height: 136rpx;
  border-radius: 999rpx;
  background: rgba(124, 92, 191, 0.1);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 8rpx;
  box-sizing: border-box;
  overflow: hidden;
}

.overall-trend-bars {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 8rpx;
}

.overall-trend-bar-wrap {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}

.overall-trend-bar-value {
  flex: none;
  margin-bottom: 4rpx;
  font-size: 18rpx;
  line-height: 1.2;
  color: $coach-purple-800;
}

.overall-trend-bar {
  flex: none;
  width: 100%;
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
  height: 156rpx;
  border-radius: 12rpx;
  overflow: hidden;
  background: repeating-linear-gradient(
    to bottom,
    rgba(124, 92, 191, 0.08) 0,
    rgba(124, 92, 191, 0.08) 1rpx,
    transparent 1rpx,
    transparent 33rpx
  );
}

.overall-trend-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.overall-trend-point {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 1;
  transform: translate(-50%, -50%);
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
