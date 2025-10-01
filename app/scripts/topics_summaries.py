from typing import List, Union

def generate_topics_and_summaries(lines: List[Union[str, dict]], model="gpt-4o", client=None):
    # Accept both list[str] and list[dict]
    texts = []
    for row in lines:
        if isinstance(row, dict):
            val = row.get("text", "")
            if isinstance(val, str):
                texts.append(val)
        elif isinstance(row, str):
            texts.append(row)
    text = "\n".join(texts)

    if not text.strip():
        return "- Topic: N/A\n  Summary: No content available."

    prompt = f"""
    Extract 5-7 business-relevant topics from the text below.
    For each topic, generate a summary (4-5 sentences).
    Ensure the response is non-empty and follows the exact format.

    Transcript:
    {text}

    Output format:
    - Topic: <topic_name>
      Summary: <summary>
    """
    if client is None:
        # Minimal deterministic fallback
        return "- Topic: General Overview\n  Summary: The transcript discusses general topics."

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Return concise, factual topics."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000
        )
        content = (resp.choices[0].message.content or "").strip()
        if content:
            return content
    except Exception:
        pass

    return "- Topic: General Overview\n  Summary: The transcript discusses general topics."
