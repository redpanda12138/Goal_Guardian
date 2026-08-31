import { test } from "node:test";
import assert from "node:assert/strict";
import { adaptiveSessionControls, blocksAdaptiveInput } from "../src/pages/chat/adaptiveSessionState.mjs";

test("upper boundary requires a choice, not another message", () => {
  const state = { workflow_mode: "adaptive_v1", session_status: "active", recovery_requested: true };
  assert.equal(blocksAdaptiveInput(state), true);
  assert.deepEqual(adaptiveSessionControls(state).map(x => x.command), ["extend", "pause", "stop"]);
});
test("paused sessions offer resume; stopped sessions never do", () => {
  const state = { workflow_mode: "adaptive_v1", session_status: "paused" };
  assert.equal(blocksAdaptiveInput(state), true);
  assert.deepEqual(adaptiveSessionControls(state).map(x => x.command), ["resume", "stop"]);
  assert.deepEqual(adaptiveSessionControls({ ...state, stop_requested: true }), []);
});
test("active long sessions are still writable and legacy is unchanged", () => {
  assert.equal(blocksAdaptiveInput({ workflow_mode: "adaptive_v1", session_status: "active", turn_index: 22 }), false);
  assert.equal(blocksAdaptiveInput({ workflow_mode: "legacy" }), false);
  assert.deepEqual(adaptiveSessionControls({ workflow_mode: "legacy" }), []);
});
