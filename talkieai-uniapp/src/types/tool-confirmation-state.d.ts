declare module "@/pages/chat/toolConfirmationState.mjs" {
  import type {
    ToolConfirmationState,
    ToolExecutionResult,
    PersistedToolConfirmation,
    ToolRequest,
  } from "@/models/models";

  export function createToolConfirmationState(
    persisted: PersistedToolConfirmation,
  ): ToolConfirmationState;
  export function confirmationPayload(state: ToolConfirmationState): {
    action_id: string;
    confirmed: true;
  };
  export function markConfirmationSubmitting(
    state: ToolConfirmationState,
  ): ToolConfirmationState;
  export function markConfirmationCancelling(
    state: ToolConfirmationState,
  ): ToolConfirmationState;
  export function cancellationPayload(state: ToolConfirmationState): {
    action_id: string;
    confirmed: false;
  };
  export function resolveCancellation(
    state: ToolConfirmationState,
    result: { action_id: string; action_status: "cancelled" } | null,
    transportError?: unknown,
  ): ToolConfirmationState;
  export function resolveToolExecution(
    state: ToolConfirmationState,
    result: ToolExecutionResult | null,
    transportError?: unknown,
  ): { state: ToolConfirmationState; assistantMessage: string };
  export function blocksConversation(state?: ToolConfirmationState | null): boolean;
  export function toolConfirmationCopy(request: ToolRequest): {
    title: string;
    detail: string;
    confirmLabel: string;
  };
}
