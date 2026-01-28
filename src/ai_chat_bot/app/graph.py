"""LangGraph orchestration.

MVP graph:
- Load recent turns from SQLite (conversation so far)
- Load core behavior prompt from file (static, versioned)
- Assemble prompt
- Call Ollama
"""

from __future__ import annotations

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from ai_chat_bot.core.config import settings, load_core_behavior
from ai_chat_bot.infra.llm.ollama_client import chat
from ai_chat_bot.infra.db.sqlite import fetch_recent_turns


class State(TypedDict, total=False):
    """State passed through the graph."""
    chat_id: str
    user_name: str
    user_text: str
    chat_type: str

    # outputs
    prompt_used: str
    assistant_text: str


def _build_prompt(*, state: State, core_behavior: str, history: list[tuple[str, str]]) -> str:
    """Assemble a single prompt string for Ollama /api/generate.

    Note: DB 'memory' is intentionally not included yet (you want that later).
    """
    chat_id = state.get("chat_id", "unknown")
    chat_type = state.get("chat_type", "unknown")
    user_name = state.get("user_name", "unknown")
    user_text = (state.get("user_text") or "").strip()

    sections: list[str] = []

    # 1) Core behavior (static, versioned file)
    cb = (core_behavior or "").strip()
    if cb:
        sections.append("### CORE BEHAVIOR\n" + cb)

    # 2) Chat context
    sections.append(
        "### CHAT CONTEXT\n"
        f"- chat_id: {chat_id}\n"
        f"- chat_type: {chat_type}\n"
        f"- user_name: {user_name}\n"
    )

    # 3) Conversation so far
    hist_lines: list[str] = []
    for u, a in history:
        u = (u or "").strip()
        a = (a or "").strip()
        if not u or not a:
            continue
        hist_lines.append(f"User: {u}\nAssistant: {a}")
    if hist_lines:
        sections.append("### CONVERSATION SO FAR\n" + "\n\n".join(hist_lines))

    # 4) New message
    sections.append("### NEW MESSAGE\n" f"User: {user_text}\nAssistant:")

    return "\n\n".join(sections).strip()


def llm_node(state: State) -> State:
    """Build prompt from recent turns + core behavior and call the model."""
    history = fetch_recent_turns(state["chat_id"], limit=settings.HISTORY_LIMIT)
    core_behavior = load_core_behavior()

    prompt = _build_prompt(state=state, core_behavior=core_behavior, history=history)
    reply = chat(prompt)

    return {"assistant_text": reply, "prompt_used": prompt}


def build_graph():
    g = StateGraph(State)
    g.add_node("llm", llm_node)
    g.add_edge(START, "llm")
    g.add_edge("llm", END)
    return g.compile()
