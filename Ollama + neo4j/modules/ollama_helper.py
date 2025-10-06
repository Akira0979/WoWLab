import subprocess

def ask_llama(prompt: str, model: str = "llama3") -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        return "Invalid prompt."
    try:
        proc = subprocess.run(
            ["ollama", "run", model],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        return proc.stdout.decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"Error calling Ollama: {e}"