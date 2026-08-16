# MAS Tool Confirmation Frontend Validation

## Scope

This phase connected the existing authenticated write-tool execution endpoint
to the uni-app chat interface. It added explicit user confirmation for
`mark_goal_complete` and `reschedule_review` requests. Read tools remain
automatic in the backend workflow and the legacy chat path is unchanged.

## Implemented Interaction

1. Versioned tool requests and execution results have explicit frontend types.
2. A deterministic client state machine validates confirmation-gated write
   tools, turn indices, execution result versions, and tool-name continuity.
3. Each proposed write is rendered inside the assistant message with an exact
   action description and separate Cancel and Confirm buttons.
4. Submission disables both buttons and blocks new chat input, preventing a
   double submission or an out-of-order user turn.
5. A confirmed request calls `/mas/workflow/tools/execute` with `confirmed:true`
   and the graph turn index. The returned GRA continuation is appended to the
   current chat and the coach dashboard is refreshed.
6. Cancellation is local and explicitly states that no change was made.
7. A transport error, malformed response, contract-version mismatch, or
   tool-name mismatch enters an indeterminate state. The UI blocks another
   write and asks the user to refresh the chat instead of retrying an action
   whose outcome may already have been committed.

The confirmation card uses the existing coach-purple design tokens, native
buttons, visible status text, `aria-live`, accessible labels, disabled states,
and mobile-width wrapping. Synthetic continuation messages do not expose
translation, collection, or copy actions that require a persisted message ID.

## Verification

- Tool confirmation state tests: 8 passed.
- Backend tool executor, workflow, and handler contract tests: 24 passed.
- H5 production build: succeeded.
- The built H5 bundle contains the confirmation component and interaction copy.
- `git diff --check`: no whitespace errors.

The standard `npm run type-check` remains blocked by existing generated
`src/**/*.vue.js` files while `allowJs` is disabled. A diagnostic run with
`allowJs` exposed the repository's existing strict-type backlog; after the
new API request type was corrected, filtering that output to this phase's files
showed only the pre-existing `messages.auto_text_shadow` error in
`src/pages/chat/index.vue`.

## Runtime Validation Boundary

The `browser-testing-with-devtools` skill was selected because this is a
browser-facing change. Chrome DevTools MCP was not configured in the current
session and the project does not include Playwright or Puppeteer, so DOM,
accessibility-tree, screenshot, and live authenticated network verification
could not be performed. No claim of real-browser visual validation is made.

The pending confirmation metadata currently exists in the live response state
rather than a dedicated database record. Reloading before resolving the prompt
can therefore remove the interactive control. Persisting and restoring pending
action metadata, plus controlled authenticated browser testing at 320, 768,
1024, and 1440 pixel widths, remain follow-up work before production rollout.
