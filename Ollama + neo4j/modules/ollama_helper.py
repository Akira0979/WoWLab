'''import subprocess

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
        return f"Error calling Ollama: {e}" '''
        
import requests

class NIMChatClient:
    def __init__(self, api_key, api_base="https://integrate.api.nvidia.com/v1", model="meta/llama-3.1-70b-instruct"):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.endpoints = [
            f"{self.api_base}/chat/completions",
        ]

    def ask_llama(self, prompt: str, temperature=0.3, retries=3, delay=5) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        for endpoint in self.endpoints:
            for attempt in range(retries):
                try:
                    response = requests.post(endpoint, headers=headers, json=data, timeout=30)
                    if response.status_code == 404:
                        continue  # Try next endpoint
                    response.raise_for_status()
                    ai_response = response.json()
                    if "choices" in ai_response and ai_response["choices"]:
                        return ai_response["choices"][0]["message"]["content"]
                    else:
                        return "AI response unavailable."
                except requests.exceptions.RequestException as e:
                    if "429" in str(e):
                        import time
                        wait_time = min(delay * (2 ** attempt), 15)
                        print(f"Rate limit hit. Retrying in {wait_time} seconds... ({attempt + 1}/{retries})")
                        time.sleep(wait_time)
                    else:
                        print(f"Error calling NVIDIA NIM: {e}")
                        return "AI response unavailable."
        return "Failed to get data."

# --- Hardcode your API key here ---
NVIDIA_API_KEY = "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"

# --- Create a global client instance ---
nim_client = NIMChatClient(NVIDIA_API_KEY)

# --- Drop-in replacement function ---
def ask_llama(prompt: str, model: str = "meta/llama-3.1-70b-instruct") -> str:
    nim_client.model = model
    return nim_client.ask_llama(prompt)
