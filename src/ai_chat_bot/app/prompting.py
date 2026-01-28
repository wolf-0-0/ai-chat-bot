from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class ChatContext:
    chat_id: str
    chat_type: str
    user_name: str
    user_id: int | None = None
    locale: str | None = None

@dataclass(frozen=True)
class MemoryItem:
    kind: str          # e.g. "fact", "preference", "task", "summary"
    content: str       # human-readable memory text
    weight: int = 1    # optional: prioritize what stays when trimming

def build_prompt(
    *,
    chat: ChatContext,
    user_text: str,
    core_behavior: str,
    memory: Iterable[MemoryItem] = (),
    history: list[tuple[str, str]] = (),
    max_chars: int = 18_000,
) -> str:
    """
    Assemble a single prompt string for /api/generate.
    The caller supplies core_behavior (file contents), memory (db), history (db).
    """

    sections: list[str] = []

    # 1) Core behavior (static, versioned)
    core_behavior = (core_behavior or "").strip()
    if core_behavior:
        sections.append("### CORE BEHAVIOR\n" + core_behavior)

    # 2) Chat context (light metadata, useful for behavior)
    sections.append(
        "### CHAT CONTEXT\n"
        f"- chat_id: {chat.chat_id}\n"
        f"- chat_type: {chat.chat_type}\n"
        f"- user_name: {chat.user_name}\n"
        + (f"- user_id: {chat.user_id}\n" if chat.user_id is not None else "")
        + (f"- locale: {chat.locale}\n" if chat.locale else "")
    )

    # 3) Memory (db)
    mem_lines: list[str] = []
    for m in memory:
        c = (m.content or "").strip()
        if not c:
            continue
        mem_lines.append(f"- [{m.kind}] {c}")
    if mem_lines:
        sections.append("### MEMORY\n" + "\n".join(mem_lines))

    # 4) Conversation so far (recent turns)
    hist_lines: list[str] = []
    for u, a in history:
        u = (u or "").strip()
        a = (a or "").strip()
        if not u or not a:
            continue
        hist_lines.append(f"User: {u}\nAssistant: {a}")
    if hist_lines:
        sections.append("### CONVERSATION SO FAR\n" + "\n\n".join(hist_lines))

    # 5) New message
    sections.append("### NEW MESSAGE\n" f"User: {user_text.strip()}\nAssistant:")

    prompt = "\n\n".join(sections).strip()

    # Hard trim (simple, effective). Later we can do smarter “drop lowest weight memory first”.
    if len(prompt) > max_chars:
        prompt = prompt[-max_chars:]

    return prompt
