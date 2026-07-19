declare module "@/pages/chat/toolConfirmationState.mjs" {
  import type {
    ToolConfirmationState,
    ToolExecutionResult,
    ToolRequest,
  } from "@/models/models";

  export function createToolConfirmationState(
    request: ToolRequest,
    turnIndex: number,
  ): ToolConfirmationState;
  export function confirmationPayload(state: ToolConfirmationState): {
    tool_request: ToolRequest;
    confirmed: true;
    turn_index: number;
  };
  export function markConfirmationSubmitting(
    state: ToolConfirmationState,
  ): ToolConfirmationState;
  export function markConfirmationCancelled(
    state: ToolConfirmationState,
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
