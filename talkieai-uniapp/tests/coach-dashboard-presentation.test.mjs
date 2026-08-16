import test from "node:test";
import assert from "node:assert/strict";

import {
  nextWorkoutDetails,
  nextWorkoutTitle,
} from "../src/components/coachDashboardPresentation.mjs";

test("Plan and Next Workout share the AI-generated short title", () => {
  const workout = {
    summary: "Walk 30 minutes three times this week",
    short_title: "Weekly Walking Routine",
    scheduled_display: "This week",
    duration_min: 30,
    activity_type: "walk",
  };

  assert.equal(nextWorkoutTitle(workout), "Weekly Walking Routine");
  assert.equal(
    nextWorkoutDetails(workout),
    "This week · 30 min · Walk",
  );
});

test("legacy dashboard data still renders a compact title", () => {
  const workout = {
    summary: "Stretch for 10 minutes every day",
    activity_type: "stretch",
  };

  assert.equal(nextWorkoutTitle(workout), "Stretch Plan");
});
