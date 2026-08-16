export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000
export const MAS_CHAT_REQUEST_TIMEOUT_MS = 120_000

const MAS_CHAT_PATH = /^\/sessions\/[^/]+\/chat(?:\?.*)?$/

export function requestTimeoutFor(url) {
  return MAS_CHAT_PATH.test(url) ? MAS_CHAT_REQUEST_TIMEOUT_MS : DEFAULT_REQUEST_TIMEOUT_MS
}

export function createActionGate() {
  let active = false

  return {
    enter() {
      if (active) return false
      active = true
      return true
    },
    leave() {
      active = false
    },
    get active() {
      return active
    },
  }
}

export function isRequestTimeoutError(error) {
  const message = String(error?.errMsg || error?.message || error || '')
  return /timed?\s*out|timeout/i.test(message)
}
