import faiss
from scripts.embedding_faiss import embed_text

def query_index(question, index, chunks, client, top_k=5, context_window=2):
    question = (question or "").strip()
    if not question:
        return []

    # Embed the question
    q_emb = embed_text([question], client=client)
    faiss.normalize_L2(q_emb)

    # Search FAISS index
    D, I = index.search(q_emb, top_k)

    # Build context ranges
    ranges = []
    for score, idx in zip(D[0], I[0]):
        if 0 <= idx < len(chunks):
            start = max(0, idx - context_window)
            end = min(len(chunks), idx + context_window + 1)
            ranges.append((start, end, float(score)))

    # Sort ranges by start
    ranges.sort()

    # Merge overlapping ranges
    merged = []
    for start, end, score in ranges:
        if not merged or start > merged[-1]["end"]:
            merged.append({"start": start, "end": end, "score": score})
        else:
            # Merge overlapping
            merged[-1]["end"] = max(merged[-1]["end"], end)
            merged[-1]["score"] = max(merged[-1]["score"], score)  # take max score

    # Build final results
    results = []
    for m in merged:
        text = " ".join(chunks[i]["text"] for i in range(m["start"], m["end"]))
        first_chunk = chunks[m["start"]]
        last_chunk = chunks[m["end"] - 1]
        results.append({
            "score": m["score"],
            "chunk_id": [chunks[i].get("chunk_id") for i in range(m["start"], m["end"])],
            "text": text,
            "start_page": first_chunk.get("start_page"),
            "start_line": first_chunk.get("start_line"),
            "end_page": last_chunk.get("end_page"),
            "end_line": last_chunk.get("end_line"),
            "section": first_chunk.get("section"),
            "speaker": first_chunk.get("speaker"),
            "role": first_chunk.get("role"),
        })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def _format_answer(answer_text, retrieved):
    answer_text = (answer_text or "").strip()
    if not answer_text:
        answer_text = "I'm unable to find a confident answer in the provided transcript."
    def format_src(c):
        sp, sl, ep, el = c.get("start_page"), c.get("start_line"), c.get("end_page"), c.get("end_line")
        if sp is None:
            return f"Chunk {c.get('chunk_id')}"
        if sp == ep:
            return f"p.{sp} L{sl}-{el} (Chunk {c.get('chunk_id')})"
        return f"p.{sp} L{sl} - p.{ep} L{el} (Chunk {c.get('chunk_id')})"
    sources = [format_src(c) for c in retrieved] if retrieved else []
    confidence = max([c["score"] for c in retrieved], default=0.0)
    return {"answer": answer_text, "sources": sources, "confidence": confidence}

def generate_answer(question, retrieved_chunks, client, model="gpt-4o"):
    if not retrieved_chunks:
        return _format_answer("I'm unable to find relevant context for this question.", retrieved_chunks)

    context_text = "\n\n".join([
        f"[{c['chunk_id']}] (p.{c.get('start_page')} L{c.get('start_line')} - p.{c.get('end_page')} L{c.get('end_line')}) {c['text']}"
        for c in retrieved_chunks
    ])
    prompt = f"""
    You are a careful assistant. Answer the question strictly using the context.
    - Keep the answer concise (4-5 sentences), factual, and avoid fabrications.
    - Do not mention being an AI model and Don't hallucinate new stuff.

    Context:
    {context_text}

    Question:
    {question}

    Answer:
    """
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Be concise, factual, and avoid hallucinations."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )
        content = (resp.choices[0].message.content or "").strip()
        return _format_answer(content, retrieved_chunks)
    except Exception:
        return _format_answer("I'm unable to generate an answer at the moment.", retrieved_chunks)
