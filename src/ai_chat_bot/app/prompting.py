def build_prompt(user_text: str, user_name: str, chat_type: str | None, history: list[tuple[str, str]]) -> str:
    """
    history = list of (user_text, assistant_text) pairs, oldest -> newest
    """

    system = (
        "You are a helpful assistant.\n"
        "Rules:\n"
        "- Be clear and brief.\n"
        "- If you don't know, say so.\n"
    )

    header = f"User: {user_name}\nChatType: {chat_type or 'unknown'}\n"

    # Build a compact transcript
    transcript_lines = []
    for u, a in history:
        transcript_lines.append(f"User: {u}")
        transcript_lines.append(f"Assistant: {a}")

    transcript = "\n".join(transcript_lines).strip()
    if transcript:
        transcript = "Conversation so far:\n" + transcript + "\n"

    new_msg = f"User: {user_text}\nAssistant:"

    return system + "\n" + header + "\n" + transcript + new_msg
