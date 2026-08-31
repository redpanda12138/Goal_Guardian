export function adaptiveSessionControls(state) {
  if (state?.workflow_mode !== "adaptive_v1" || state.session_status === "completed") return [];
  if (state.stop_requested) return [];
  const controls = state.session_status === "paused"
    ? [{ command: "resume", label: "Resume" }]
    : [{ command: "pause", label: "Pause" }];
  if (state.session_status === "active" && state.recovery_requested) {
    controls.unshift({ command: "extend", label: "Two more replies" });
  }
  controls.push({ command: "stop", label: "End session" });
  return controls;
}

export function blocksAdaptiveInput(state) {
  return state?.workflow_mode === "adaptive_v1" &&
    (state.session_status !== "active" || state.recovery_requested === true);
}
