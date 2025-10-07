from typing import Dict, List

def init_history(session: Dict):
    session.setdefault("chat_history", [])

def get_history(session: Dict) -> List[Dict]:
    return session.get("chat_history", [])

def append_turn(session: Dict, role: str, content: str):
    history = session.setdefault("chat_history", [])
    history.append({"role": role, "content": content})
    session["chat_history"] = history  # ensure writeback

def clear_history(session: Dict):
    session["chat_history"] = []

def set_current_doc(session: Dict, doc_meta: Dict):
    session["current_doc"] = doc_meta

def get_current_doc(session: Dict) -> Dict:
    return session.get("current_doc")
