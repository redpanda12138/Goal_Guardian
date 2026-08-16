import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  MAS_CHAT_REQUEST_TIMEOUT_MS,
  createActionGate,
  isRequestTimeoutError,
  requestTimeoutFor,
} from '../src/utils/chatRequestPolicy.mjs'

test('MAS chat requests allow enough time for multi-agent model calls', () => {
  assert.equal(DEFAULT_REQUEST_TIMEOUT_MS, 30_000)
  assert.equal(MAS_CHAT_REQUEST_TIMEOUT_MS, 120_000)
  assert.equal(requestTimeoutFor('/sessions/session-123/chat'), 120_000)
  assert.equal(requestTimeoutFor('/users/me'), 30_000)
})

test('action gate rejects duplicate work until the active request finishes', () => {
  const gate = createActionGate()

  assert.equal(gate.enter(), true)
  assert.equal(gate.enter(), false)
  assert.equal(gate.active, true)

  gate.leave()
  assert.equal(gate.active, false)
  assert.equal(gate.enter(), true)
})

test('timeout errors can be distinguished from definitive send failures', () => {
  assert.equal(isRequestTimeoutError({ errMsg: 'request:fail timeout' }), true)
  assert.equal(isRequestTimeoutError(new Error('Request timed out')), true)
  assert.equal(isRequestTimeoutError({ errMsg: 'request:fail network error' }), false)
})
