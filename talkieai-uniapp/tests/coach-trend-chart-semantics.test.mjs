import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const componentsDir = path.resolve(testDir, "../src/pages/practice/components");
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

test("renders line and area trends separately from grouped bars", () => {
  assert.match(chartSource, /type ChartType = "bar" \| "line" \| "area"/);
  assert.match(chartSource, /v-if="chartType === 'bar'"/);
  assert.match(chartSource, /<polyline[\s\S]*?v-if="hasTrend"/);
  assert.match(chartSource, /<polygon[\s\S]*?chartType === 'area' && hasTrend/);
});

test("explains why a single review cannot form a trend", () => {
  assert.match(chartSource, /lineCoordinates\.value\.length > 1/);
  assert.match(
    chartSource,
    /More weekly reviews are required to establish a trend\./
  );
});
