from typing import List, Dict
from modules.ollama_helper import ask_llama

SYSTEM_INSTRUCTIONS = (
    "You are a helpful RFP assistant. Ground answers in provided context and cite filenames when relevant. "
    "Be concise and specific. If unsure, say what’s missing."
)

def format_prompt(history: List[Dict], context: str, question: str) -> str:
    hist_str = ""
    for turn in history[-10:]:  # last 10 turns
        role = turn["role"]
        content = turn["content"].replace("\n", " ").strip()
        hist_str += f"{role.upper()}: {content}\n"
    return (
        f"SYSTEM: {SYSTEM_INSTRUCTIONS}\n\n"
        f"CHAT HISTORY:\n{hist_str}\n"
        f"CONTEXT:\n{context}\n\n"
        f"USER: {question}\n\n"
        "ASSISTANT:"
    )

def answer_with_llm(history: List[Dict], context: str, question: str, model: str = "llama3") -> str:
    prompt = format_prompt(history, context, question)
    return ask_llama(prompt, model=model)