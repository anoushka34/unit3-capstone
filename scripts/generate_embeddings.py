"""
generate_embeddings.py

Implements the Bronze requirement: "Sentence Transformers generates document
embeddings" (Bedrock's embedding models are confirmed denied for this
sandbox - see README). Runs entirely locally, no API key or AWS permission
needed.

Also implements a local semantic search index (cosine similarity over the
embeddings) as a substitute for OpenSearch, since OpenSearch write access
has not been confirmed in this sandbox. Documented as a substitute, not a
claim that OpenSearch itself was used.

Install once:
    pip install sentence-transformers numpy --break-system-packages
"""

import csv
import json
import numpy as np
from sentence_transformers import SentenceTransformer

CSV_PATH = "data/data.csv"
OUTPUT_PATH = "data/lyrics_embeddings.json"
CHUNK_SIZE_WORDS = 150   # approx 500-750 tokens depending on tokenizer; adjust if needed
MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, good general-purpose model

model = SentenceTransformer(MODEL_NAME)


def chunk_text(text: str, chunk_size_words: int = CHUNK_SIZE_WORDS):
    """Splits text into word-count-based chunks (500-1000 token range per assignment spec)."""
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), chunk_size_words):
        chunk = " ".join(words[i:i + chunk_size_words])
        chunks.append(chunk)
    return chunks


def load_rows(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_embedding_store(csv_path: str = CSV_PATH, output_path: str = OUTPUT_PATH):
    from tqdm import tqdm

    rows = load_rows(csv_path)
    print(f"Loaded {len(rows)} rows. Chunking lyrics...")

    # First pass: build all chunks across all rows, tracking which song each came from.
    all_chunks = []
    chunk_meta = []  # (doc_id, chunk_index) parallel to all_chunks

    for row in tqdm(rows, desc="Chunking"):
        song = row.get("song name", "unknown")
        artist = row.get("artist name", "unknown")
        lyrics = row.get("lyrics", "").strip()

        if not lyrics:
            continue

        chunks = chunk_text(lyrics)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            chunk_meta.append((f"{artist} - {song}", i))

    print(f"Encoding {len(all_chunks)} chunks in a single batched pass (this is the slow part - progress bar below)...")

    # Second pass: encode everything in one batched call instead of per-row calls.
    # batch_size controls memory/speed tradeoff; 64 is a safe default on CPU.
    embeddings = model.encode(
        all_chunks,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=64,
    )

    store = []
    for (doc_id, chunk_index), text, emb in zip(chunk_meta, all_chunks, embeddings):
        store.append({
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "text": text,
            "embedding": emb.tolist(),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(store, f)

    print(f"\nGenerated {len(store)} embedded chunks from {len(rows)} rows.")
    print(f"Saved to {output_path}")
    return store


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def semantic_search(query: str, store_path: str = OUTPUT_PATH, top_k: int = 3):
    """
    Local semantic search substitute for OpenSearch: embeds the query,
    compares against all stored chunk embeddings via cosine similarity,
    and returns the top_k most relevant chunks with their source.
    """
    with open(store_path, "r", encoding="utf-8") as f:
        store = json.load(f)

    query_embedding = model.encode(query, convert_to_numpy=True)

    scored = []
    for item in store:
        chunk_embedding = np.array(item["embedding"])
        score = cosine_similarity(query_embedding, chunk_embedding)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    results = []
    for score, item in top_results:
        results.append({
            "score": round(score, 4),
            "source": item["doc_id"],
            "chunk_index": item["chunk_index"],
            "text_preview": item["text"][:200] + ("..." if len(item["text"]) > 200 else ""),
        })
    return results


if __name__ == "__main__":
    print("Building embedding store from data.csv lyrics column...\n")
    build_embedding_store()

    print("\n--- Test semantic search ---")
    test_query = "singing about love and dancing"
    results = semantic_search(test_query)
    print(f"Query: '{test_query}'\n")
    for r in results:
        print(f"  [{r['score']}] {r['source']} (chunk {r['chunk_index']})")
        print(f"    {r['text_preview']}\n")