"""
Flask RAG App — loads pre-built FAISS index + chunks from disk
and serves a search UI.

Run:
    python app.py

Prerequisites:
    1. Run the notebook first to generate rag_artifacts/
    2. pip install flask faiss-cpu numpy ollama
    3. Ollama must be running with the embedding model pulled
"""

import json, os, textwrap
from pathlib import Path

import numpy as np
import faiss
import ollama
from flask import Flask, render_template, request, jsonify

# ── Ollama client (bypass SSL/proxy issues) ──────────────────────────────
ollama_client = ollama.Client(host="http://localhost:11434", trust_env=False)

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "rag_artifacts"

# ── Load artifacts once at startup ───────────────────────────────────────
print("Loading artifacts …")

with open(ARTIFACTS_DIR / "config.json") as f:
    config = json.load(f)

EMBED_MODEL = config["EMBED_MODEL"]
WORDS_PER_CHUNK = config["WORDS_PER_CHUNK"]
TOPK = config["TOPK"]

with open(ARTIFACTS_DIR / "chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

emb = np.load(str(ARTIFACTS_DIR / "embeddings.npy"))
index = faiss.read_index(str(ARTIFACTS_DIR / "faiss_index.bin"))

print(
    f"  Loaded {len(chunks)} chunks, embeddings {emb.shape}, FAISS index {index.ntotal} vectors"
)
print(f"  Embed model: {EMBED_MODEL}")

# ── Lookup map for neighbor expansion ────────────────────────────────────
KEY_TO_IDX = {(c["source_path"], c["chunk_index"]): gi for gi, c in enumerate(chunks)}


# ── Core RAG helpers (same logic as notebook) ────────────────────────────
def l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return mat / norms


def expand_with_neighbors_simple(I, chunks, neighbors=1, max_out=8):
    """
    For each ANN hit in I[0], build ONE window containing the hit itself
    plus its ±neighbor chunks from the same document, joined into a single
    text block. Returns one context dict per hit. `max_out` caps the total
    chunks across all returned windows.
    """
    contexts = []
    total_chunks = 0

    for gi in I[0]:
        c = chunks[int(gi)]
        doc = c["source_path"]
        ci = c["chunk_index"]

        # Collect the hit + its available neighbors (skip ones that fall
        # outside the document boundary).
        window_idxs = []
        for delta in range(-neighbors, neighbors + 1):
            j = KEY_TO_IDX.get((doc, ci + delta))
            if j is not None:
                window_idxs.append(j)

        if not window_idxs:
            continue

        # Sort so the merged text reads in document order.
        window_idxs.sort(key=lambda j: chunks[j]["chunk_index"])

        text = "\n\n".join(chunks[j]["text"] for j in window_idxs)
        contexts.append(
            {
                "title": c["title"],
                "source_path": doc,
                "hit_chunk_index": ci,                                       # the original ANN match
                "start_chunk": chunks[window_idxs[0]]["chunk_index"],
                "end_chunk": chunks[window_idxs[-1]]["chunk_index"],
                "text": text,
                "approx_words": sum(len(chunks[j]["text"].split()) for j in window_idxs),
            }
        )
        total_chunks += len(window_idxs)
        if total_chunks >= max_out:
            break

    return contexts


def search_windowed(query: str, topk: int = TOPK, max_out: int = 8):
    q_vec = np.asarray(
        ollama_client.embeddings(model=EMBED_MODEL, prompt=query)["embedding"],
        dtype="float32",
    )
    q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-12)
    D, I = index.search(q_vec.reshape(1, -1), topk)

    neighbors = 1 if WORDS_PER_CHUNK >= 260 else 2

    top1 = float(D[0][0])
    top2 = float(D[0][1]) if len(D[0]) > 1 else 0.0
    margin = top1 - top2
    init_topk = 1 if (top1 >= 0.35 and margin >= 0.05) else min(3, topk)

    I_init = np.array([I[0][:init_topk]])

    contexts = expand_with_neighbors_simple(
        I_init, chunks, neighbors=neighbors, max_out=max_out
    )

    hits = []
    for score, idx_ in zip(D[0].tolist(), I[0].tolist()):
        m = chunks[idx_]
        hits.append(
            {
                "score": round(score, 3),
                "id": m["id"],
                "title": m["title"],
                "source_path": m["source_path"],
                "chunk_index": m["chunk_index"],
                "preview": (
                    (m["preview"][:300] + "…")
                    if len(m["preview"]) > 300
                    else m["preview"]
                ),
            }
        )
    return hits, contexts


# ── Flask app ────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "index.html", embed_model=EMBED_MODEL, num_chunks=len(chunks)
    )


@app.route("/search", methods=["POST"])
def search():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    try:
        hits, contexts = search_windowed(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "query": query,
            "hits": hits,
            "contexts": [
                {
                    "title": c["title"],
                    "source": Path(c["source_path"]).name,
                    "hit_chunk_index": c["hit_chunk_index"],
                    "start_chunk": c["start_chunk"],
                    "end_chunk": c["end_chunk"],
                    "approx_words": c["approx_words"],
                    "text": c["text"],
                }
                for c in contexts
            ],
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)


# flask --app hello_flask.py run
