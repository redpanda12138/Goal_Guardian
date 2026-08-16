declare module "@/utils/chatRequestPolicy.mjs" {
  export const DEFAULT_REQUEST_TIMEOUT_MS: number;
  export const MAS_CHAT_REQUEST_TIMEOUT_MS: number;

  export function requestTimeoutFor(url: string): number;
  export function isRequestTimeoutError(error: unknown): boolean;
  export function createActionGate(): {
    enter(): boolean;
    leave(): void;
    readonly active: boolean;
  };
}
