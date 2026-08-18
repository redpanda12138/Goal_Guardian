import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const componentsDir = path.resolve(testDir, "../src/pages/practice/components");
const practicePageSource = readFileSync(
  path.resolve(componentsDir, "../index.vue"),
  "utf8"
);
const reviewCardSource = readFileSync(
  path.join(componentsDir, "CoachOverallReviewCard.vue"),
  "utf8"
);
const chartSource = readFileSync(
  path.join(componentsDir, "CoachOverallTrendChart.vue"),
  "utf8"
);

test("maps each progress metric to a chart type suited to its meaning", () => {
  assert.match(
    reviewCardSource,
    /title="Completion Rate Trend"[\s\S]*?chart-type="line"[\s\S]*?:y-max="100"[\s\S]*?value-suffix="%"/
  );
  assert.match(
    reviewCardSource,
    /title="Plan vs Done Trend"[\s\S]*?chart-type="bar"[\s\S]*?:has-secondary="true"/
  );
  assert.match(
    reviewCardSource,
    /title="Cumulative Progress Trend"[\s\S]*?chart-type="area"/
  );
});

test("renders line and area trends with an App-compatible canvas", () => {
  assert.match(chartSource, /type ChartType = "bar" \| "line" \| "area"/);
  assert.match(chartSource, /v-if="chartType === 'bar'"/);
  assert.match(chartSource, /<canvas[\s\S]*?:canvas-id="canvasId"/);
  assert.match(chartSource, /uni\.createCanvasContext\(canvasId, componentInstance\)/);
  assert.match(chartSource, /context\.moveTo\([\s\S]*?context\.lineTo\([\s\S]*?context\.stroke\(\)/);
  assert.match(chartSource, /chartType === "area"[\s\S]*?context\.closePath\(\)[\s\S]*?context\.fill\(\)/);
  assert.doesNotMatch(chartSource, /<(?:svg|polyline|polygon)\b/);
});

test("redraws after tab visibility changes and keeps points on the canvas path", () => {
  assert.match(practicePageSource, /<CoachOverallReviewCard[\s\S]*?:active="tabNum === '1'"/);
  assert.match(reviewCardSource, /active\?:\s*boolean/);
  assert.match(
    reviewCardSource,
    /<CoachOverallTrendChart[\s\S]*?:active="active"/
  );
  assert.match(chartSource, /active\?:\s*boolean/);
  assert.match(
    chartSource,
    /watch\(\s*\(\)\s*=>\s*props\.active[\s\S]*?scheduleDraw/
  );
  assert.match(chartSource, /context\.arc\(/);
  assert.match(chartSource, /context\.fillText\(/);
  assert.doesNotMatch(chartSource, /class="overall-trend-point"/);
});

test("uses an opaque-enough area fill and narrow grouped bars", () => {
  assert.match(
    chartSource,
    /setFillStyle\("rgba\(124,\s*58,\s*237,\s*0\.(?:2[5-9]|[3-9]\d?)\)"\)/
  );
  assert.match(chartSource, /\.overall-trend-bar\s*\{[\s\S]*?width:\s*(?:1[6-9]|2[0-2])rpx/);
});

test("shows grouped bar values and keeps every chart inside its card", () => {
  assert.match(chartSource, /\{\{\s*item\.primaryValue\s*\}\}/);
  assert.match(chartSource, /\{\{\s*item\.secondaryValue\s*\}\}/);
  assert.match(chartSource, /const HORIZONTAL_PADDING_PERCENT = 10/);
  assert.match(chartSource, /overflow:\s*hidden/);
  assert.doesNotMatch(chartSource, /overflow:\s*visible/);
});

test("explains why a single review cannot form a trend", () => {
  assert.match(chartSource, /lineCoordinates\.value\.length > 1/);
  assert.match(
    chartSource,
    /More weekly reviews are required to establish a trend\./
  );
});
