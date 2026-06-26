"""T2.1 — LLM client (summarize + embed)."""
import json, os, struct
from typing import Optional
import httpx
from pydantic import BaseModel, Field

class LLMError(Exception): pass

class _Experience(BaseModel):
    kind: str = "lesson"; title: str = ""; content: str = ""

class LLMOutput(BaseModel):
    summary: str = Field(default="", max_length=400)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    experiences: list[_Experience] = Field(default_factory=list, max_length=5)

class LLMClient:
    def __init__(self, base_url=None, api_key=None, model=None):
        self.base_url = (base_url or os.getenv("MBCLAW_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("MBCLAW_LLM_API_KEY", "")
        self.model = model or os.getenv("MBCLAW_LLM_MODEL", "gpt-4o-mini")

    def summarize_session(self, messages):
        if not self.api_key or self.api_key == "sk-xxx":
            if os.getenv("MBCLAW_LLM_MOCK", "0") == "1": return self._summarize_mock()
            return LLMOutput()
        text = "\n".join([f"[{m.get('role','')}]: {m.get('content','')[:500]}" for m in messages[-40:]])
        prompt = [{"role":"system","content":"Summarize as JSON with summary(max 400), keywords(max 10), experiences(max 5, each with kind/success|failure|lesson, title, content). Output only JSON."},
                  {"role":"user","content":text}]
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return LLMOutput(summary=data.get("summary","")[:400], keywords=data.get("keywords",[])[:10],
                experiences=[_Experience(**e) for e in data.get("experiences",[])][:5])
        except: return LLMOutput(summary=raw[:400])

    def embed(self, text):
        eu = (os.getenv("MBCLAW_EMBEDDING_BASE_URL", self.base_url)).rstrip("/")
        ek = os.getenv("MBCLAW_EMBEDDING_API_KEY", self.api_key)
        em = os.getenv("MBCLAW_EMBEDDING_MODEL", "text-embedding-3-small")
        try:
            r = httpx.post(f"{eu}/embeddings",
                headers={"Authorization":f"Bearer {ek}","Content-Type":"application/json"},
                json={"input":text,"model":em}, timeout=30)
            if r.status_code == 200: return r.json()["data"][0]["embedding"]
        except: pass
        return [0.0] * 1536

    def _call(self, messages):
        for _ in range(2):
            try:
                r = httpx.post(f"{self.base_url}/chat/completions",
                    headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                    json={"model":self.model,"messages":messages,"temperature":0.3,"max_tokens":2048}, timeout=60)
                if r.status_code == 200: return r.json()["choices"][0]["message"]["content"]
            except: pass
        raise LLMError("LLM call failed")

    def _summarize_mock(self):
        return LLMOutput(summary="[mock] summary", keywords=["test"], experiences=[_Experience(kind="lesson",title="mock",content="mock")])

def get_llm():
    return LLMClient()

def encode_embedding(vec):
    return struct.pack(f'{len(vec)}f', *vec)

def decode_embedding(blob):
    import numpy as np
    return np.frombuffer(blob, dtype=np.float32).tolist()
