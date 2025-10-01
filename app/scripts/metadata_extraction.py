from typing import List, Dict, Any
import json
from json_repair import repair_json
from scripts.rag_query import query_index


def repair_and_load_json(res):
    res_json = []
    try:
        res_json = json.loads(res)
    except json.JSONDecodeError:
        try:
            res_ = res.replace("'", '"')
            res_json = json.loads(res_)
        except json.JSONDecodeError:
            try:
                res_repaired = repair_json(res)
                res_json = json.loads(res_repaired)
            except json.JSONDecodeError:
                pass
    return res_json

def extract_document_metadata(lines: List[dict], chunks: List[dict], index, embedding_client, chat_client) -> Dict[str, Any]:
    # Build header context (first ~2 pages) to capture title block and date
    header_lines = [r.get("text", "") for r in lines if (r.get("page") or 0) <= 2][:400]
    header_context = "\n".join(header_lines)

    # Retrieval contexts for each field
    field_queries = {
        "company": "What is the company name of the earnings call transcript?",
        "ceo": "Who is the CEO or main management person speaking on the call?",
        "call_date": "What is the date of the call? Return a human-readable date.",
        "ticker": "What is the company ticker if mentioned?",
        "participants": "List the key management participants with their roles (e.g., CEO, CFO)."
    }

    # Only allow chunks where chunk_id contains "Metadata"
    allowed_chunks = [c for c in chunks if "Metadata" in str(c.get("chunk_id", ""))]

    contexts: Dict[str, str] = {"header": header_context}
    for key, q in field_queries.items():
        retrieved = query_index(q, index, allowed_chunks, client=embedding_client, top_k=8)
        ctx = "\n\n".join([r.get("text", "") for r in retrieved])
        contexts[key] = ctx


    system = (
        "You extract factual metadata from earnings call context. "
        "Use the header context when available. If unknown, return null. "
        "Return strict JSON with keys: company, ceo, call_date, ticker, participants (array of strings)."
    )
    user = "\n\n".join([f"[{k.upper()} CONTEXT]\n{v}" for k, v in contexts.items()])
    prompt = (
        "Extract metadata from the contexts. If a value is not present, use null.\n"
        "Return ONLY JSON."
    )

    try:
        resp = chat_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=500,
        )
        import json
        content = (resp.choices[0].message.content or "").strip()
        data = repair_and_load_json(content)
    except Exception:
        data = {"company": None, "ceo": None, "call_date": None, "ticker": None, "participants": []}

    total_pages = max((r.get("page") or 0) for r in lines) if lines else 0
    data["total_pages"] = total_pages
    return data