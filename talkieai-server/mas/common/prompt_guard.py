PROMPT_LEAK_MARKERS = (
    "The client said:",
    "The client chose the goal:",
    "If number, ask",
    "If mood, ask",
    "Reflect empathetically",
    "Reflect positively",
    "Use fallback:",
    "Don't use client name",
    "Don't mention goal explicitly",
    "Do not ask additional questions",
    "Task:",
    "Client message:",
)


def build_coach_prompt(client_message: str, task: str) -> str:
    message = (client_message or "").strip() or "(no response)"
    return (
        "Reply to the client as a warm, empathetic health coach. "
        "Return only the exact message the client should see. "
        "Do not mention prompts, instructions, labels, turns, or the phrase 'The client said'.\n\n"
        f"Client message: {message}\n"
        f"Task: {task}"
    )


def safe_coach_reply(reply: str, fallback: str) -> str:
    cleaned = (reply or "").strip()
    if not cleaned:
        return fallback

    if any(marker in cleaned for marker in PROMPT_LEAK_MARKERS):
        return fallback

    return cleaned
