const WRITE_TOOLS = new Set(["mark_goal_complete", "reschedule_review"]);
const TERMINAL_STATUSES = new Set(["completed", "cancelled", "failed"]);

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requirePending(state) {
  if (!state || state.status !== "pending") {
    throw new Error("tool confirmation is not pending");
  }
}

export function createToolConfirmationState(request, turnIndex) {
  if (!isPlainObject(request) || request.contract_version !== "v1") {
    throw new Error("invalid tool confirmation contract");
  }
  if (!WRITE_TOOLS.has(request.tool_name)) {
    throw new Error("tool confirmation must target a write tool");
  }
  if (request.requires_confirmation !== true || !isPlainObject(request.arguments)) {
    throw new Error("write tool must require confirmation and object arguments");
  }
  if (!Number.isInteger(turnIndex) || turnIndex < 0 || turnIndex > 15) {
    throw new Error("tool confirmation turn index must be between 0 and 15");
  }
  return {
    request,
    turnIndex,
    status: "pending",
    error: "",
  };
}

export function confirmationPayload(state) {
  requirePending(state);
  return {
    tool_request: state.request,
    confirmed: true,
    turn_index: state.turnIndex,
  };
}

export function markConfirmationSubmitting(state) {
  requirePending(state);
  return { ...state, status: "submitting", error: "" };
}

export function markConfirmationCancelled(state) {
  requirePending(state);
  return { ...state, status: "cancelled", error: "" };
}

export function resolveToolExecution(state, result, transportError = null) {
  if (!state || state.status !== "submitting") {
    throw new Error("tool confirmation is not submitting");
  }
  if (transportError || !isPlainObject(result)) {
    return {
      state: {
        ...state,
        status: "indeterminate",
        error: "The result could not be verified. Refresh the chat before continuing.",
      },
      assistantMessage: "",
    };
  }
  if (result.contract_version !== "v1") {
    return resolveToolExecution(state, null, new Error("contract mismatch"));
  }
  if (result.tool_name !== state.request.tool_name) {
    return resolveToolExecution(state, null, new Error("tool mismatch"));
  }

  const assistantMessage =
    typeof result.assistant_message === "string"
      ? result.assistant_message.trim()
      : "";
  if (result.status === "succeeded" && assistantMessage) {
    return {
      state: { ...state, status: "completed", error: "" },
      assistantMessage,
    };
  }
  if (result.status === "failed" || result.status === "skipped") {
    return {
      state: {
        ...state,
        status: "failed",
        error: "The requested change was not completed.",
      },
      assistantMessage,
    };
  }
  return resolveToolExecution(state, null, new Error("invalid result"));
}

export function blocksConversation(state) {
  return Boolean(
    state && !TERMINAL_STATUSES.has(state.status),
  );
}

export function toolConfirmationCopy(request) {
  if (request.tool_name === "mark_goal_complete") {
    const goalIndex = Number(request.arguments.goal_index);
    return {
      title: `Mark goal ${goalIndex + 1} complete?`,
      detail:
        typeof request.arguments.note === "string"
          ? request.arguments.note
          : "This will update your saved goal progress.",
      confirmLabel: "Mark complete",
    };
  }
  return {
    title: "Reschedule the weekly review?",
    detail: String(request.arguments.date || "Choose the proposed review time."),
    confirmLabel: "Reschedule",
  };
}
