import test from "node:test";
import assert from "node:assert/strict";

import {
  blocksConversation,
  confirmationPayload,
  createToolConfirmationState,
  markConfirmationCancelled,
  markConfirmationSubmitting,
  resolveToolExecution,
  toolConfirmationCopy,
} from "../src/pages/chat/toolConfirmationState.mjs";

const request = {
  contract_version: "v1",
  tool_name: "mark_goal_complete",
  arguments: { goal_index: 1, note: "Completed after lunch" },
  requires_confirmation: true,
};

test("creates a pending state only for confirmation-gated write tools", () => {
  const state = createToolConfirmationState(request, 8);
  assert.equal(state.status, "pending");
  assert.equal(state.turnIndex, 8);
  assert.equal(blocksConversation(state), true);
  assert.throws(
    () => createToolConfirmationState({ ...request, tool_name: "get_weekly_progress" }, 8),
    /write tool/,
  );
});

test("builds the execution payload without changing arguments", () => {
  const state = createToolConfirmationState(request, 8);
  assert.deepEqual(confirmationPayload(state), {
    tool_request: request,
    confirmed: true,
    turn_index: 8,
  });
});

test("a submitting state cannot be submitted twice", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(request, 8),
  );
  assert.equal(submitting.status, "submitting");
  assert.throws(() => markConfirmationSubmitting(submitting), /not pending/);
  assert.throws(() => confirmationPayload(submitting), /not pending/);
});

test("cancel is local, final, and unblocks the conversation", () => {
  const cancelled = markConfirmationCancelled(
    createToolConfirmationState(request, 8),
  );
  assert.equal(cancelled.status, "cancelled");
  assert.equal(blocksConversation(cancelled), false);
});

test("successful execution records the continuation and prevents another write", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(request, 8),
  );
  const resolved = resolveToolExecution(submitting, {
    contract_version: "v1",
    tool_name: "mark_goal_complete",
    status: "succeeded",
    assistant_message: "Goal 2 has been marked complete.",
  });
  assert.equal(resolved.state.status, "completed");
  assert.equal(resolved.assistantMessage, "Goal 2 has been marked complete.");
  assert.equal(blocksConversation(resolved.state), false);
  assert.throws(() => confirmationPayload(resolved.state), /not pending/);
});

test("an invalid execution contract is treated as indeterminate", () => {
  const submitting = markConfirmationSubmitting(
    createToolConfirmationState(request, 8),
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
    createToolConfirmationState(request, 8),
  );
  const resolved = resolveToolExecution(submitting, null, new Error("timeout"));
  assert.equal(resolved.state.status, "indeterminate");
  assert.equal(blocksConversation(resolved.state), true);
  assert.match(resolved.state.error, /refresh/i);
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
