"""One-time corpus ingest: download a few Project Gutenberg books, chunk them,
embed with OpenAI, and add them to Chroma. Idempotent — re-running is a no-op once
the collection is populated (the "embed once" idea from the RAG demo notebook).

Run it once Chroma is reachable. Locally (Act 1), point it at the published port:
    CHROMA_HOST=localhost CHROMA_PORT=8001 python ingest.py
(or, against the Compose stack: docker compose run --rm api python ingest.py)
"""

import os, json
from dotenv import load_dotenv
import subprocess, time
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from mcp import ClientSession


import textwrap


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



import os
import re

import requests
import chromadb
from openai import OpenAI

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))
COLLECTION  = os.environ.get("CHROMA_COLLECTION", "rag_demo")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")

WORDS_PER_CHUNK = 300
OVERLAP_WORDS   = 60
EMBED_BATCH     = 64

# A small slice of the reference corpus — add more titles from the RAG notebook.
GUTENBERG_BOOKS = {
    #"Moby-Dick": "https://www.gutenberg.org/files/2701/2701-0.txt",
    #"Pride and Prejudice": "https://www.gutenberg.org/files/1342/1342-0.txt",
    #"Frankenstein": "https://www.gutenberg.org/files/84/84-0.txt",
    #"Alice in Wonderland": "https://www.gutenberg.org/cache/epub/11/pg11.txt",
    #"Dracula": "https://www.gutenberg.org/files/345/345-0.txt",
    "A Tale of Two Cities": "https://www.gutenberg.org/files/98/98-0.txt",
    "The Great Gatsby": "https://www.gutenberg.org/cache/epub/64317/pg64317.txt",
    "Adventures of Sherlock Holmes": "https://www.gutenberg.org/files/1661/1661-0.txt",
    #"War and Peace": "https://www.gutenberg.org/files/2600/2600-0.txt",
    #"Jane Eyre": "https://www.gutenberg.org/files/1260/1260-0.txt",
    #"The Picture of Dorian Gray": "https://www.gutenberg.org/files/174/174-0.txt",
    #"Crime and Punishment": "https://www.gutenberg.org/files/2554/2554-0.txt",
    #"Wuthering Heights": "https://www.gutenberg.org/files/768/768-0.txt"
}

oai = OpenAI()
chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
# Chroma stores whatever vectors we give it; no embedding model lives in the DB.
collection = chroma.get_or_create_collection(
    COLLECTION, metadata={"hnsw:space": "cosine"}    # cosine distance: lower = closer
)

# Idempotency guard: if we already have vectors, do nothing.
if collection.count() > 0:
    print(f"'{COLLECTION}' already holds {collection.count()} vectors — nothing to do.")
    raise SystemExit(0)

# Project Gutenberg wraps each book in license boilerplate; keep only the body.
START_MARK = re.compile(r"\*\*\* START OF (THIS|THE) PROJECT GUTENBERG EBOOK .* \*\*\*", re.I)
END_MARK   = re.compile(r"\*\*\* END OF (THIS|THE) PROJECT GUTENBERG EBOOK .* \*\*\*", re.I)

session = requests.Session()
session.trust_env = False            # don't route the download through a proxy/VPN

# 1) Download + 2) chunk each book into overlapping word windows.
chunks = []
for title, url in GUTENBERG_BOOKS.items():
    print(f"Downloading {title} ...")
    raw = session.get(url, timeout=180).text
    s, e = START_MARK.search(raw), END_MARK.search(raw)
    if s and e and e.start() > s.end():
        raw = raw[s.end():e.start()]

    doc_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    words = re.sub(r"\s+", " ", raw).strip().split()
    step = max(1, WORDS_PER_CHUNK - OVERLAP_WORDS)
    idx = 0
    for start in range(0, len(words), step):
        window = words[start:start + WORDS_PER_CHUNK]
        if len(window) < max(60, WORDS_PER_CHUNK // 4):
            break
        chunks.append({
            "id": f"{doc_id}#{idx}",           # Chroma takes string ids directly
            "doc_id": doc_id, "chunk_index": idx, "title": title,
            "source": url, "text": " ".join(window),
        })
        idx += 1
        if start + WORDS_PER_CHUNK >= len(words):
            break

print(f"Built {len(chunks)} chunks from {len(GUTENBERG_BOOKS)} books. Embedding with {EMBED_MODEL} ...")

# 3) Embed in batches and 4) add to Chroma (documents + metadata + our vectors).
spans = range(0, len(chunks), EMBED_BATCH)
for span in (tqdm(list(spans), desc="Embedding") if tqdm else spans):
    batch = chunks[span:span + EMBED_BATCH]
    vectors = [d.embedding for d in
               oai.embeddings.create(model=EMBED_MODEL, input=[c["text"] for c in batch]).data]
    collection.add(
        ids=[c["id"] for c in batch],
        embeddings=vectors,
        documents=[c["text"] for c in batch],
        metadatas=[{"doc_id": c["doc_id"], "chunk_index": c["chunk_index"],
                    "title": c["title"], "source": c["source"]} for c in batch],
    )

print(f"Done. '{COLLECTION}' now holds {collection.count()} vectors.")
