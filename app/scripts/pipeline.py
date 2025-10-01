from dotenv import load_dotenv
import os
import streamlit as st
from scripts.extract_text import extract_pdf_text
from scripts.chunking import chunk_metadata , speaker_level_chunks
from scripts.section_split import split_transcript_metadata_opening_qa
from scripts.embedding_faiss import embed_text, build_faiss_index
from scripts.topics_summaries import generate_topics_and_summaries
from scripts.topics_parser import parse_topics_block
from scripts.rag_query import query_index, generate_answer
from scripts.cache_utils import (
    compute_doc_id, get_cache_dir, path_in_cache,
    has_cached_artifacts, save_json, load_json, save_numpy, load_numpy,
    save_faiss, load_faiss
)
from openai import AzureOpenAI
from rapidfuzz import fuzz
import faiss
from scripts.metadata_extraction import extract_document_metadata

load_dotenv()

# --------------------------
# Initialize clients from environment
# --------------------------
import streamlit as st
import os

AZURE_OPENAI_API_KEY = st.secrets["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_ENDPOINT = st.secrets.get("AZURE_OPENAI_ENDPOINT", "https://agents-general.openai.azure.com")
AZURE_OPENAI_CHAT_COMPLETION_VERSION = st.secrets.get("AZURE_OPENAI_CHAT_COMPLETION_VERSION", "2024-08-01-preview")
AZURE_OPENAI_EMBEDDINGS_VERSION = st.secrets.get("AZURE_OPENAI_EMBEDDINGS_VERSION", "2023-05-15")
CHAT_MODEL = st.secrets.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
EMBEDDING_MODEL = st.secrets.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
CACHE_BASE = st.secrets.get("EMBEDDINGS_CACHE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data"))
CACHE_BASE = os.path.abspath(CACHE_BASE)
os.makedirs(CACHE_BASE, exist_ok=True)

if not AZURE_OPENAI_API_KEY:
    raise RuntimeError("AZURE_OPENAI_API_KEY is not set in the environment.")

# Chat client
chat_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_CHAT_COMPLETION_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Embeddings client
embedding_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_EMBEDDINGS_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# --------------------------
# Main processing function
# --------------------------
def process_transcript(pdf_file, chunk_size=500, overlap=50):
    """
    Process a transcript PDF end-to-end with disk cache by document hash.
    Accepts an uploaded file object from Streamlit.
    """

    # Compute document hash for cache key
    file_bytes = pdf_file.read()
    pdf_file.seek(0)
    print("PDF Read Completed")
    doc_id = compute_doc_id(file_bytes)
    cache_dir = get_cache_dir(CACHE_BASE, doc_id)

    # Fast-path: load from cache if available
    if has_cached_artifacts(cache_dir):
        sections = load_json(path_in_cache(cache_dir, "sections.json"))
        chunks = load_json(path_in_cache(cache_dir, "chunks.json"))
        prelim_summary = load_json(path_in_cache(cache_dir, "summary.json"))
        topics_summaries = load_json(path_in_cache(cache_dir, "topics_summaries.json"))
        topics_items = load_json(path_in_cache(cache_dir, "topics_items.json"))
        index = load_faiss(path_in_cache(cache_dir, "faiss.index"))
        return {
            "doc_id": doc_id,
            "cache_hit": True,
            "sections": sections,
            "summary": prelim_summary,
            "chunks": chunks,
            "topics_summaries": topics_summaries,
            "topics_items": topics_items,
            "faiss_index": index,
            "embedding_client": embedding_client,
            "chat_client": chat_client,
            "chat_model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL
        }

    # Step 1: Extract text
    transcript_lines = extract_pdf_text(pdf_file)  # returns list of dict lines

    print("Text Extracted")

    # Step 2: Split into sections
    metadata, opening_remarks_lines, qa_lines = split_transcript_metadata_opening_qa(transcript_lines)

    sections = {
        "Opening Remarks": opening_remarks_lines,
        "Q&A": qa_lines
    }
    print("Sections Split")

    all_chunks = []
    chunk_id = 0

    # 1️⃣ Metadata chunks (500 words, 50 overlap)
    metadata_chunks, chunk_id = chunk_metadata(metadata, chunk_size=500, overlap=50, start_chunk_id=chunk_id)
    all_chunks.extend(metadata_chunks)

    # 2️⃣ Speaker-level chunks for Opening Remarks + Q&A
    for section_name, lines in sections.items():
        section_chunks, chunk_id , state = speaker_level_chunks(lines, section=section_name, start_chunk_id=chunk_id)
        all_chunks.extend(section_chunks)

    print("Chunks Created")

    # Step 4.5: Initial document metadata (for management participants) after chunking but before index
    # Build a temporary minimal index for robust field extraction
    tmp_embeddings = embed_text([chunk["text"] for chunk in all_chunks], client=embedding_client)
    tmp_index = build_faiss_index(tmp_embeddings)
    prelim_summary = extract_document_metadata(transcript_lines, all_chunks, tmp_index, embedding_client, chat_client)

    # Use participants list to mark management speakers
    management_names = set()
    for p in (prelim_summary.get("participants") or []):
        # keep the name part before comma/role if present
        name = p.split(",")[0].strip()
        if name:
            management_names.add(name.lower())

    # Filter out moderator lines were already skipped during chunking; now set roles by rule
    print(management_names)

    for c in all_chunks:
        spk = (c.get("speaker") or "").lower()
        
        if c.get("section") == "Q&A":
            if spk and any(fuzz.partial_ratio(spk, m.lower()) >= 80 for m in management_names):
                c["role"] = "answer"
            else:
                c["role"] = "question"

    # Step 4: Generate topics and summaries per section (needed for per-topic sources)
    topics_summaries = {}
    topics_items = {}
    for section_name, lines in sections.items():
        block = generate_topics_and_summaries(
            lines, client=chat_client
        )
        topics_summaries[section_name] = block
        items = parse_topics_block(block)
        topics_items[section_name] = items
    print("Topics and Summaries Generated")

    # Step 5: Embed chunks and build FAISS index
    embeddings = embed_text([chunk["text"] for chunk in all_chunks], client=embedding_client)
    index = build_faiss_index(embeddings)
    print("FAISS Index Built")

    # Step 8: Per-topic provenance using index (map each topic+summary to top chunks)
    per_topic_sources = {}
    for section_name, items in topics_items.items():
        section_sources = []
        for item in items:
            q = f"{item.get('topic','')}. {item.get('summary','')}".strip()
            if not q:
                section_sources.append([])
                continue
            q_emb = embed_text([q], client=embedding_client)
            faiss.normalize_L2(q_emb)
            D, I = index.search(q_emb, 3)
            topic_results = []
            for score, idx_i in zip(D[0], I[0]):
                if 0 <= idx_i < len(all_chunks):
                    c = all_chunks[idx_i]
                    if (c.get("role") or "").lower() == "moderator":
                        continue
                    topic_results.append({
                        "chunk_id": c.get("chunk_id"),
                        "score": float(score),
                        "start_page": c.get("start_page"),
                        "start_line": c.get("start_line"),
                        "end_page": c.get("end_page"),
                        "end_line": c.get("end_line"),
                    })
            section_sources.append(topic_results)
        per_topic_sources[section_name] = section_sources

    # Save to cache
    save_json(path_in_cache(cache_dir, "sections.json"), sections)
    save_json(path_in_cache(cache_dir, "chunks.json"), all_chunks)
    save_json(path_in_cache(cache_dir, "summary.json"), prelim_summary)
    save_json(path_in_cache(cache_dir, "topics_summaries.json"), topics_summaries)
    save_json(path_in_cache(cache_dir, "topics_items.json"), topics_items)
    save_faiss(path_in_cache(cache_dir, "faiss.index"), index)
    print("Cache Saved")

    # Return full processed structure
    return {
        "doc_id": doc_id,
        "cache_hit": False,
        "summary": prelim_summary,
        "sections": sections,
        "chunks": all_chunks,
        "topics_summaries": topics_summaries,
        "topics_items": topics_items,
        "faiss_index": index,
        "embedding_client": embedding_client,
        "chat_client": chat_client,
        "chat_model": CHAT_MODEL,
        "embedding_model": EMBEDDING_MODEL
    }
