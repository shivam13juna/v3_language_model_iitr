
"""Flask RAG service: retrieve from Chroma, answer with OpenAI.

Wired to two backends via environment config (see compose.yaml / .env):
  - Chroma  (vector DB)             via CHROMA_HOST / CHROMA_PORT
  - OpenAI  (embeddings + chat LLM) via OPENAI_API_KEY
"""
import os

from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import chromadb

import os, json
from dotenv import load_dotenv
import subprocess, time
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from mcp import ClientSession


import textwrap

import truststore
truststore.inject_into_ssl()

def pretty_print(*args):
    text = " ".join(str(arg) for arg in args)
    try:
        print(textwrap.fill(text, width=80))
    except Exception as e:
        print(text)  # fallback to normal print if text is not a string

        

load_dotenv('/Users/shivam13juna/Documents/scaler/iitr_classes/llm_ref/openai_key.env')  # reads .env file in the current directory

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        "OPENAI_API_KEY not found! "
        "Make sure you have a .env file with: OPENAI_API_KEY=sk-..."
    )

pretty_print("API key loaded successfully.")

# ---- Config: everything is overridable via the environment / .env ----
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))
COLLECTION  = os.environ.get("CHROMA_COLLECTION", "rag_demo")
CHAT_MODEL  = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
TOP_K       = int(os.environ.get("TOP_K", "5"))

app = Flask(__name__)

# Clients are built once at import and reused across requests.
oai = OpenAI()                       # reads OPENAI_API_KEY from the environment
chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
# We always hand Chroma our own (OpenAI) vectors, so it needs no embedding model.
collection = chroma.get_or_create_collection(
    COLLECTION, metadata={"hnsw:space": "cosine"}   # cosine distance: lower = closer
)


def embed(text):
    """Turn one piece of text into an embedding vector via OpenAI."""
    resp = oai.embeddings.create(model=EMBED_MODEL, input=[text])
    return resp.data[0].embedding


def answer(question):
    """Retrieve the nearest chunks from Chroma, then ask the LLM to answer
    ONLY from that context (citing [doc_id#chunk] for each claim)."""
    res = collection.query(
        query_embeddings=[embed(question)], n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )
    # We sent one query, so the results live at index [0].
    docs  = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]

    context = ""
    for text, meta in zip(docs, metas):
        context += f"[{meta['doc_id']}#{meta['chunk_index']}] {meta['title']}\n{text}\n---\n"

    system_prompt = (
        "You are a helpful assistant. Answer ONLY using the provided context. "
        "If the answer is not in the context, say: "
        "'I don't know based on the provided context.' "
        "Cite sources in square brackets like [doc_id#chunk_index] for each key claim."
    )
    resp = oai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
        ],
    )
    return resp.choices[0].message.content, metas, dists


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    """Readiness probe: is Chroma reachable and the collection populated?"""
    try:
        return {"status": "ok", "vectors": collection.count()}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}, 503


@app.post("/ask")
def ask():
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": 'POST JSON like {"question": "..."}'}), 400
    try:
        text, metas, dists = answer(question)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({
        "question": question,
        "answer": text,
        "sources": [
            {"id": f"{m['doc_id']}#{m['chunk_index']}",
             "title": m["title"], "distance": round(d, 4)}
            for m, d in zip(metas, dists)
        ],
    })


if __name__ == "__main__":
    # Dev server only — the container runs gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=8000)
