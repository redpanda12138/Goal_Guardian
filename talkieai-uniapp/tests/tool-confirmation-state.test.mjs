import test from "node:test";
import assert from "node:assert/strict";

import {
  blocksConversation,
  cancellationPayload,
  confirmationPayload,
  createToolConfirmationState,
  markConfirmationCancelling,
  markConfirmationSubmitting,
  resolveCancellation,
  resolveToolExecution,
  toolConfirmationCopy,
} from "../src/pages/chat/toolConfirmationState.mjs";

const request = {
  contract_version: "v1",
  tool_name: "mark_goal_complete",
  arguments: { goal_index: 1, note: "Completed after lunch" },
  requires_confirmation: true,
};

const persisted = {
  action_id: "action-123",
  tool_request: request,
  turn_index: 8,
  status: "pending",
};

test("long adaptive sessions can restore a confirmation after turn fifteen", () => {
  assert.equal(createToolConfirmationState({ ...persisted, turn_index: 20 }).turnIndex, 20);
});

test("a terminal tool success remains successful when dialogue is paused", () => {
  const state = markConfirmationSubmitting(createToolConfirmationState(persisted));
  const result = resolveToolExecution(state, {
    contract_version: "v1", tool_name: "mark_goal_complete", status: "succeeded",
    action_id: persisted.action_id, action_status: "completed", session_status: "paused",
    assistant_message: "",
  });
  assert.equal(result.state.status, "completed");
  assert.equal(result.assistantMessage, "");
});

test("creates a pending state only for confirmation-gated write tools", () => {
  const state = createToolConfirmationState(persisted);
  assert.equal(state.status, "pending");
  assert.equal(state.actionId, "action-123");
  assert.equal(state.turnIndex, 8);
  assert.equal(blocksConversation(state), true);
  assert.throws(
    () => createToolConfirmationState({
      ...persisted,
      tool_request: { ...request, tool_name: "get_weekly_progress" },
    }),
    /write tool/,
  );
});

test("builds the execution payload without changing arguments", () => {
  const state = createToolConfirmationState(persisted);
  assert.deepEqual(confirmationPayload(state), {
    action_id: "action-123",
    confirmed: true,
  });
});

test("a submitting state cannot be submitted twice", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(persisted),
  );
  assert.equal(submitting.status, "submitting");
  assert.throws(() => markConfirmationSubmitting(submitting), /not pending/);
  assert.throws(() => confirmationPayload(submitting), /not pending/);
});

test("cancel is persisted before it becomes final", () => {
  const cancelling = markConfirmationCancelling(createToolConfirmationState(persisted));
  assert.deepEqual(cancellationPayload(cancelling), {
    action_id: "action-123",
    confirmed: false,
  });
  const cancelled = resolveCancellation(cancelling, {
    action_id: "action-123",
    action_status: "cancelled",
  });
  assert.equal(cancelled.status, "cancelled");
  assert.equal(blocksConversation(cancelled), false);
});

test("successful execution records the continuation and prevents another write", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(persisted),
  );
  const resolved = resolveToolExecution(submitting, {
    contract_version: "v1",
    tool_name: "mark_goal_complete",
    status: "succeeded",
    action_id: "action-123",
    action_status: "completed",
    assistant_message: "Goal 2 has been marked complete.",
  });
  assert.equal(resolved.state.status, "completed");
  assert.equal(resolved.assistantMessage, "Goal 2 has been marked complete.");
  assert.equal(blocksConversation(resolved.state), false);
  assert.throws(() => confirmationPayload(resolved.state), /not pending/);
});

test("an invalid execution contract is treated as indeterminate", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(persisted),
  );
  const resolved = resolveToolExecution(submitting, {
    contract_version: "v2",
    tool_name: "mark_goal_complete",
    status: "succeeded",
    assistant_message: "Untrusted result",
  });

  assert.equal(resolved.state.status, "indeterminate");
  assert.equal(resolved.assistantMessage, "");
});

test("transport ambiguity is final and blocks further turns until refresh", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(persisted),
  );
  const resolved = resolveToolExecution(submitting, null, new Error("timeout"));
  assert.equal(resolved.state.status, "indeterminate");
  assert.equal(blocksConversation(resolved.state), true);
  assert.match(resolved.state.error, /refresh/i);
});

test("refresh restores terminal server state and treats executing as indeterminate", () => {
  assert.equal(
    createToolConfirmationState({ ...persisted, status: "cancelled" }).status,
    "cancelled",
  );
  const executing = createToolConfirmationState({ ...persisted, status: "executing" });
  assert.equal(executing.status, "indeterminate");
  assert.equal(blocksConversation(executing), true);
});

test("copy describes the exact proposed write", () => {
  assert.deepEqual(toolConfirmationCopy(request), {
    title: "Mark goal 2 complete?",
    detail: "Completed after lunch",
    confirmLabel: "Mark complete",
  });
  assert.equal(
    toolConfirmationCopy({
      contract_version: "v1",
      tool_name: "reschedule_review",
      arguments: { date: "2026-07-26T09:00:00+08:00" },
      requires_confirmation: true,
    }).title,
    "Reschedule the weekly review?",
  );
});
