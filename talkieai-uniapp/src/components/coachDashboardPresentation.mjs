function compactWords(value, maximum = 5) {
  return String(value || "")
    .trim()
    .replace(/[.,;:!?]+$/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, maximum)
    .join(" ");
}

function displayActivity(value) {
  const activity = String(value || "").trim();
  return activity ? activity.charAt(0).toUpperCase() + activity.slice(1) : "";
}

export function nextWorkoutTitle(workout) {
  if (!workout?.summary) return "No workout scheduled yet";

  const aiTitle = compactWords(workout.short_title);
  if (aiTitle) return aiTitle;

  const activity = displayActivity(workout.activity_type);
  if (activity) return `${activity} Plan`;

  return compactWords(workout.summary, 4) || "Weekly Activity Plan";
}

export function nextWorkoutDetails(workout) {
  if (!workout?.summary) return "";
  const schedule = String(workout.scheduled_display || "").trim();
  const duration = workout.duration_min ? `${workout.duration_min} min` : "";
  const activity = displayActivity(workout.activity_type);
  return [schedule, duration, activity].filter(Boolean).join(" · ");
}
