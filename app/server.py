"""
FastAPI server — sustainable remedies chatbot.

Flow
----
1. Accept POST /api/chat  { query, mode?, persona? }
2. Classify query as "remedy" or "general".
3. Search the ChromaDB vector store for relevant remedy context.
4. If there is a strong match  →  build prompt with context  →  Ollama  (free, local).
5. If Ollama fails or there is no good match  →  OpenAI  (cloud fallback).
6. Return { route, source, answer, matches? }.

Also serves the static frontend at /.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure app/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_engine import RAGEngine, RELEVANCE_THRESHOLD  # noqa: E402

# ---------------------------------------------------------------------------
# Import inference helpers from existing infer.py
# ---------------------------------------------------------------------------
from infer import (  # noqa: E402
    PERSONAS,
    answer_with_ollama,
    answer_with_openai,
    is_remedy_query,
)

# ---------------------------------------------------------------------------
# Config (env-overridable)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = os.getenv("DATASET_PATH", str(PROJECT_ROOT / "raw_data" / "merged_dataset.json"))
VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", str(PROJECT_ROOT / "vectorstore"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
OPENAI_KEY_PATH = os.getenv("OPENAI_KEY_PATH", str(PROJECT_ROOT / "openai_api_key.txt"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
RELEVANCE_DIST = float(os.getenv("RELEVANCE_THRESHOLD", str(RELEVANCE_THRESHOLD)))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# ---------------------------------------------------------------------------
# Lifespan: warm up the RAG engine once
# ---------------------------------------------------------------------------
rag: Optional[RAGEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag
    rag = RAGEngine(persist_dir=VECTORSTORE_DIR)
    if rag.count() == 0:
        print("[server] Vector store empty — indexing dataset …")
        n = rag.index_dataset(DATASET_PATH)
        print(f"[server] Indexed {n} records.")
    else:
        print(f"[server] Vector store ready — {rag.count()} records.")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Sustainable Remedies Chatbot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("auto", pattern="^(auto|general|remedy)$")
    persona: str = Field("knowledge", pattern="^(knowledge|wellness)$")


class ChatResponse(BaseModel):
    route: str
    source: str
    answer: str
    rag_matches: int = 0
    rag_best_distance: Optional[float] = None


# ---------------------------------------------------------------------------
# Prompt builder (adapted from infer.py to accept external context)
# ---------------------------------------------------------------------------
def _build_prompt(query: str, persona: str, route: str, rag_context: str) -> str:
    persona_data = PERSONAS.get(persona, PERSONAS["knowledge"])
    mode_hint = (
        "If this is a home-remedy question, answer with safe, practical steps and a short caution."
        if route == "remedy"
        else "Answer as a general assistant. Do not force home-remedy advice unless the user asks for it."
    )
    parts = [
        persona_data["prompt_template"],
        f"Response style: {persona_data['response_style']}",
        mode_hint,
    ]
    if rag_context:
        parts.append("Retrieved remedy context (use only information that is directly relevant):\n" + rag_context)
    parts.append(f"User question: {query}\n\nAssistant:")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def _answer(query: str, mode: str, persona: str) -> ChatResponse:
    # 1. Route
    if mode == "auto":
        route = "remedy" if is_remedy_query(query) else "general"
    else:
        route = mode

    # 2. RAG retrieval
    rag_context = ""
    is_relevant = False
    rag_matches = 0
    best_dist: Optional[float] = None

    if rag is not None:
        rag_context, is_relevant = rag.retrieve_context(query, top_k=TOP_K, threshold=RELEVANCE_DIST)
        hits = rag.query(query, top_k=TOP_K)
        rag_matches = len(hits)
        if hits:
            best_dist = hits[0][1]

    prompt = _build_prompt(query, persona, route, rag_context)

    answer_text: Optional[str] = None
    source = "none"

    # 3. If dataset has a strong match → try Ollama first (free)
    if is_relevant:
        try:
            answer_text = answer_with_ollama(OLLAMA_MODEL, prompt, OLLAMA_HOST)
            if answer_text:
                source = "ollama"
        except Exception as exc:
            print(f"[ollama] failed: {exc}")

    # 4. If no Ollama answer but we have good context, try OpenAI with that context
    #    If no good match at all, try OpenAI as general knowledge fallback
    if answer_text is None:
        try:
            answer_text = answer_with_openai(prompt, OPENAI_KEY_PATH, OPENAI_MODEL)
            if answer_text:
                source = "openai"
        except Exception as exc:
            print(f"[openai] failed: {exc}")

    # 5. Last resort: if we have RAG context but no LLM worked, return context directly
    if answer_text is None and rag_context:
        answer_text = (
            "I found some relevant information in our remedy database, "
            "but couldn't reach an AI backend to format a proper answer.\n\n"
            + rag_context
        )
        source = "rag_only"

    if answer_text is None:
        answer_text = "Sorry, I could not generate an answer right now. Please try again later."
        source = "none"

    return ChatResponse(
        route=route,
        source=source,
        answer=answer_text,
        rag_matches=rag_matches,
        rag_best_distance=round(best_dist, 4) if best_dist is not None else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    return _answer(req.query, req.mode, req.persona)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "vectorstore_records": rag.count() if rag else 0,
        "ollama_host": OLLAMA_HOST,
        "openai_model": OPENAI_MODEL,
    }


@app.post("/api/reindex")
async def reindex():
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")
    rag.reset()
    n = rag.index_dataset(DATASET_PATH)
    return {"indexed": n}


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
