"""LangGraph orchestration (JSON-in/JSON-out LLM contract)."""

from __future__ import annotations

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from ai_chat_bot.core.config import settings, load_system_rules
from ai_chat_bot.app.prompting import build_llm_request
from ai_chat_bot.infra.llm.ollama_client import generate_contract
from ai_chat_bot.infra.db.sqlite import fetch_recent_events, get_user_description


class State(TypedDict, total=False):
    # inputs
    telegram_chat_id: int
    telegram_user_id: int
    user_text: str

    # outputs
    prompt_used: str
    assistant_text: str
    updated_user_description: str


def llm_node(state: State) -> State:
    chat_id = int(state["telegram_chat_id"])
    user_id = int(state["telegram_user_id"])
    user_text = (state.get("user_text") or "").strip()

    system_rules = load_system_rules()
    user_description = get_user_description(user_id)
    recent_events = fetch_recent_events(chat_id, limit_turns=settings.HISTORY_LIMIT)

    request_obj = build_llm_request(
        schema_version=settings.SCHEMA_VERSION,
        assistant_name=settings.ASSISTANT_NAME,
        system_rules=system_rules,
        timezone_name=settings.TIMEZONE,
        user_description=user_description,
        recent_events=recent_events,
        user_message=user_text,
    )

    parsed, prompt_used = generate_contract(request_obj)

    return {
        "assistant_text": parsed.get("assistant_text", ""),
        "updated_user_description": parsed.get("updated_user_description", ""),
        "prompt_used": prompt_used,
    }


def build_graph():
    g = StateGraph(State)
    g.add_node("llm", llm_node)
    g.add_edge(START, "llm")
    g.add_edge("llm", END)
    return g.compile()
