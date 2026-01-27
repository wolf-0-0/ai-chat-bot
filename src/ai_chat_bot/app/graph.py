from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from ai_chat_bot.infra.llm.ollama_client import chat
from src.ai_chat_bot.app.prompting import build_prompt
from src.ai_chat_bot.infra.db.sqlite import fetch_recent_turns

class State(TypedDict):
    chat_id: str
    user_name: str
    user_text: str
    chat_type: str
    prompt_used: str
    assistant_text: str

def llm_node(state: State):
    # Load last N turns for this chat
    history = fetch_recent_turns(state["chat_id"], limit=8)

    prompt = build_prompt(
        user_text=state["user_text"],
        user_name=state["user_name"],
        chat_type=state.get("chat_type"),
        history=history,
    )

    reply = chat(prompt)
    return {"assistant_text": reply, "prompt_used": prompt}

def build_graph():
    g = StateGraph(State)
    g.add_node("llm", llm_node)
    g.add_edge(START, "llm")
    g.add_edge("llm", END)
    return g.compile()
