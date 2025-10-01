from io import BytesIO
import streamlit as st
import warnings
import time
import markdown
import streamlit.components.v1 as components
from scripts.pipeline import process_transcript
from scripts.rag_query import query_index, generate_answer

warnings.filterwarnings("ignore")
st.set_page_config(page_title="📄 Transcript Assistant", layout="wide")
st.title("📄 Transcript Assistant")

# ---------- Initialize Session State ----------
if "docs" not in st.session_state:
    st.session_state["docs"] = []
if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = None
if "qa_cache" not in st.session_state:
    st.session_state["qa_cache"] = {}
if "focus_summary" not in st.session_state:
    st.session_state["focus_summary"] = False
if "auto_scroll_answer" not in st.session_state:
    st.session_state["auto_scroll_answer"] = False
if "generated_summary" not in st.session_state:
    st.session_state["generated_summary"] = {}  # store summaries keyed by section

# Track which docs are processed
if "processed_docs" not in st.session_state:
    st.session_state["processed_docs"] = set()

# ---------- Caching Layer ----------
@st.cache_resource(show_spinner="Processing transcript…")
def cached_process_transcript(file_bytes: bytes, file_name: str):
    """Wrap bytes in BytesIO for process_transcript."""
    return process_transcript(BytesIO(file_bytes), chunk_size=500, overlap=50)

# 2️⃣ Refresh logic right below the function
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

print(time.time() - st.session_state.last_refresh)
if time.time() - st.session_state.last_refresh > 600:  # 30 mins
    st.cache_resource.clear()
    st.session_state.last_refresh = time.time()

# ---------- Utility ----------
def _get_selected_data():
    doc_id = st.session_state.get("selected_doc_id")
    if not doc_id:
        return None

    doc = next((d for d in st.session_state["docs"] if d["id"] == doc_id), None)
    if not doc:
        return None

    # Only process if not already done
    if doc_id not in st.session_state["processed_docs"]:
        if doc.get("file") is not None:
            try:
                doc["data"] = cached_process_transcript(doc["file"].getvalue(), doc["file"].name)
                doc["status"] = "Processed"
                st.session_state["processed_docs"].add(doc_id)
            except Exception as e:
                doc["status"] = "Error"
                doc["error_msg"] = str(e)
    return doc

# ---------- Display Helpers ----------
def _display_chunk_card(c, section_name, idx):
    speaker = c.get("speaker") or "Unknown"
    label = f"{speaker}"
    if section_name == "Q&A" and c.get("role"):
        label += f" · {c['role'].title()}"
    header = f"{label} — p.{c.get('start_page')} L{c.get('start_line')} to p.{c.get('end_page')} L{c.get('end_line') }"
    with st.expander(header, expanded=False):
        text = c.get("text", "")
        st.markdown(
            f"<div style='background:#f7faff; color:#222; padding:12px; border-radius:10px; border:1px solid #dbe8ff; word-wrap:break-word;'>{text}</div>",
            unsafe_allow_html=True
        )

def _display_answer_card(ans_text):
    html_content = markdown.markdown(ans_text, extensions=['extra', 'nl2br'])
    st.markdown(
        f"<div style='background:#effaf1; color:#0b4d1a; padding:16px; "
        f"border-radius:12px; border:1px solid #cde9d6; word-wrap:break-word;'>{html_content}</div>",
        unsafe_allow_html=True
    )

# ---------- Top Navigation ----------
selected_doc = _get_selected_data()
selected_data = (selected_doc or {}).get("data") or None

label_upload = "Upload"
label_summary = "Summary"
label_open = f"Opening Remarks Section"
label_qna = f"Q&A Section"
label_chat = "Chat Assistant"

ordered = [label_upload,label_summary, label_open, label_qna, label_chat]

_tabs = st.tabs(ordered)
label_to_tab = dict(zip(ordered, _tabs))

upload_tab = label_to_tab[label_upload]
summary_tab = label_to_tab[label_summary]
opening_tab = label_to_tab[label_open]
qa_tab = label_to_tab[label_qna]
chat_tab = label_to_tab[label_chat]

with upload_tab:
    st.subheader("Upload a PDF Transcript")
    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"], key="upload_tab")
    if uploaded_file is not None:
        doc_id = f"local::{uploaded_file.name}"
        found = next((d for d in st.session_state["docs"] if d.get("id") == doc_id), None)
        if not found:
            found = {
                "id": doc_id,
                "name": uploaded_file.name,
                "file": uploaded_file,
                "status": "NotProcessed",
                "data": None,
            }
            st.session_state["docs"].append(found)
        else:
            found["file"] = uploaded_file
            found["status"] = "NotProcessed"
            found["data"] = None
        st.session_state["selected_doc_id"] = doc_id

        if found["status"] != "Processed":
            with st.spinner("Extracting text and building index…"):
                try:
                    data = cached_process_transcript(uploaded_file.getvalue(), uploaded_file.name)
                    found["data"] = data
                    found["status"] = "Processed"
                    st.success("Processed ✅. Move to Summary tab.")
                except Exception as e:
                    found["status"] = "Error"
                    found["error_msg"] = str(e)
                    st.error(f"Failed to process file: {e}")

# ---------------- Summary Tab ----------------
with summary_tab:
    sel = _get_selected_data()
    if not sel or sel.get("status") != "Processed":
        st.info("Please upload a document.")
    else:
        data = sel.get("data")
        s = data.get("summary", {})
        chunks = data.get("chunks", [])
        # Derived metrics
        num_questions = len([c for c in chunks if (c.get("section") or "") == "Q&A"])
        num_opening = len([c for c in chunks if (c.get("section") or "") == "Opening Remarks"])
        speakers = sorted(set([(c.get("speaker") or "").strip() for c in chunks if c.get("speaker")]))
        total_people = len(speakers)
        participants = s.get("participants") or []

        st.subheader("Document Summary")
        company = s.get("company") or "—"
        ceo = s.get("ceo") or "—"
        call_date = s.get("call_date") or "—"
        pages = s.get("total_pages") or 0
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.markdown("Company")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{company}</div>",
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown("CEO")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{ceo}</div>",
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown("Call Date")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{call_date}</div>",
                unsafe_allow_html=True,
            )
        with m4:
            st.markdown("Pages")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{pages}</div>",
                unsafe_allow_html=True,
            )
        with m5:
            st.markdown("Opening Remarks Chunks")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{num_opening}</div>",
                unsafe_allow_html=True,
            )
        with m6:
            st.markdown("Q&A Chunks")
            st.markdown(
                f"<div style='white-space:normal; word-break:break-word; font-size:1.4rem; font-weight:600'>{num_questions}</div>",
                unsafe_allow_html=True,
            )

        st.subheader(f"Total unique speakers : {total_people}")
        if participants:
            st.write("Management participants (from transcript):")
            for p in participants:
                st.write(f"- {p}")

# ---------------- Opening Remarks Tab ----------------
with opening_tab:
    sel = _get_selected_data()
    if not sel or sel.get("status") != "Processed":
        st.info("Please upload a document.")
    else:
        data = sel.get("data")
        st.subheader("Opening Remarks — Analysis")
        section_name = "Opening Remarks"
        section_chunks = [c for c in data["chunks"] if c.get("section") == section_name]
        st.caption(f"Total Chunks: {len(section_chunks)}")

        tab1, tab2, tab3 = st.tabs(["View Chunks", "Generate Topics", "Create Summaries"])

        with tab1:
            for idx, c in enumerate(section_chunks):
                _display_chunk_card(c, section_name, idx)

        with tab2:
            items = data.get("topics_items", {}).get(section_name, [])
            if not items:
                st.info("No topics detected.")
            else:
                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]
                for idx, item in enumerate(items):
                    topic_name = item.get("topic", f"Topic {idx+1}")
                    color = colors[idx % len(colors)]
                    st.markdown(
                        f"""
                        <div style="
                            padding: 12px; 
                            border-radius: 8px; 
                            margin-bottom: 10px; 
                            background-color: {color}; 
                            color: white;
                            font-weight: bold;
                            box-shadow: 1px 1px 5px rgba(0,0,0,0.3);
                        ">
                            {topic_name}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        with tab3:  # "Create Summaries" tab
            items = data.get("topics_items", {}).get(section_name, [])
            selected = []
            doc_id = st.session_state.get("selected_doc_id", "no_doc")

            # Ensure generated_summary dict exists and is nested by doc_id
            if "generated_summary" not in st.session_state:
                st.session_state["generated_summary"] = {}
            if doc_id not in st.session_state["generated_summary"]:
                st.session_state["generated_summary"][doc_id] = {}

            # Step 1: Display checkboxes for each topic
            for idx, item in enumerate(items):
                key = f"sel_{doc_id}_{section_name}_{idx}"
                if st.checkbox(item.get("topic", f"Topic {idx+1}"), key=key):
                    selected.append(item)

            # Step 2: Generate button
            if st.button("Generate Summary", key=f"gen_sum_{doc_id}_{section_name}"):
                if not selected:
                    st.warning("Select at least one topic.")
                else:
                    # Build summary from selected topics
                    formatted_summary = ""
                    for it in selected:
                        summary = it.get("summary", "")
                        paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
                        for para in paragraphs:
                            formatted_summary += f"{para}\n\n\n\n"

                    # Store summary under doc_id + section_name
                    st.session_state["generated_summary"][doc_id][section_name] = formatted_summary.strip()

            # Step 3: Display the stored summary (if any)
            if section_name in st.session_state["generated_summary"].get(doc_id, {}):
                _display_answer_card(st.session_state["generated_summary"][doc_id][section_name])


# ---------------- Q&A Tab ----------------
with qa_tab:
    sel = _get_selected_data()
    if not sel or sel.get("status") != "Processed":
        st.info("Please upload a document.")
    else:
        data = sel.get("data")
        st.subheader("Q&A — Analysis")
        section_name = "Q&A"
        section_chunks = [c for c in data["chunks"] if c.get("section") == section_name]
        st.caption(f"Total Chunks: {len(section_chunks)}")

        tab1, tab2, tab3 = st.tabs(["View Chunks", "Generate Topics", "Create Summaries"])

        with tab1:
            for idx, c in enumerate(section_chunks):
                _display_chunk_card(c, section_name, idx)

        with tab2:
            items = data.get("topics_items", {}).get(section_name, [])
            if not items:
                st.info("No topics detected.")
            else:
                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]
                for idx, item in enumerate(items):
                    topic_name = item.get("topic", f"Topic {idx+1}")
                    color = colors[idx % len(colors)]
                    st.markdown(
                        f"""
                        <div style="
                            padding: 12px; 
                            border-radius: 8px; 
                            margin-bottom: 10px; 
                            background-color: {color}; 
                            color: white;
                            font-weight: bold;
                            box-shadow: 1px 1px 5px rgba(0,0,0,0.3);
                        ">
                            {topic_name}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        with tab3:  # "Create Summaries" tab
            items = data.get("topics_items", {}).get(section_name, [])
            selected = []
            doc_id = st.session_state.get("selected_doc_id", "no_doc")

            # Ensure generated_summary dict exists and is nested by doc_id
            if "generated_summary" not in st.session_state:
                st.session_state["generated_summary"] = {}
            if doc_id not in st.session_state["generated_summary"]:
                st.session_state["generated_summary"][doc_id] = {}

            # Step 1: Display checkboxes for each topic
            for idx, item in enumerate(items):
                key = f"sel_{doc_id}_{section_name}_{idx}"
                if st.checkbox(item.get("topic", f"Topic {idx+1}"), key=key):
                    selected.append(item)

            # Step 2: Generate button
            if st.button("Generate Summary", key=f"gen_sum_{doc_id}_{section_name}"):
                if not selected:
                    st.warning("Select at least one topic.")
                else:
                    # Build summary from selected topics
                    formatted_summary = ""
                    for it in selected:
                        summary = it.get("summary", "")
                        paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
                        for para in paragraphs:
                            formatted_summary += f"{para}\n\n\n\n"

                    # Store summary under doc_id + section_name
                    st.session_state["generated_summary"][doc_id][section_name] = formatted_summary.strip()

            # Step 3: Display the stored summary (if any)
            if section_name in st.session_state["generated_summary"].get(doc_id, {}):
                _display_answer_card(st.session_state["generated_summary"][doc_id][section_name])


# ---------------- Chat Assistant Tab ----------------
with chat_tab:
    doc_id = st.session_state.get("selected_doc_id")
    if not doc_id:
        st.info("Please upload a document.")
        st.stop()
    sel = _get_selected_data()
    if not sel or sel.get("status") != "Processed":
        st.info("Please upload a document.")
    else:
        data = sel.get("data")
        st.subheader("AI Assistant")
        sample_qs =  [
            "What were the main drivers of revenue and earnings growth this quarter?",
            "Any comments on margins, operating costs, or profitability trends?",
            "What are the key risks, challenges, or headwinds the company faces?",
            "Any updates on capital allocation, dividends, or share repurchase plans?",
            "How is the company managing cash flow and liquidity?",
        ]
        with st.expander("Suggested Questions"):
            for idx, q in enumerate(sample_qs):
                if st.button(q, key=f"suggest_q_{idx}"):
                    st.session_state[f"chat_input_{doc_id}"] = q
                    st.session_state["auto_scroll_answer"] = True
                    st.rerun()
        question = st.text_input("Ask a question", key=f"chat_input_{doc_id}" , placeholder="Type your question here...")
        if question:
            cache_key = f"{doc_id}::{question.strip().lower()}"
            if cache_key in st.session_state["qa_cache"]:
                retrieved, ans = st.session_state["qa_cache"][cache_key]
            else:
                with st.spinner("Retrieving context and generating answer..."):
                    pool = data["chunks"]
                    pool = [c for c in pool if c.get("role","").lower() == "answer"]

                    print(len(pool))

                    retrieved = query_index(question, data["faiss_index"], pool, client=data["embedding_client"])
                    ans = generate_answer(question, retrieved, client=data["chat_client"], model=data.get("chat_model", "gpt-4o"))
                st.session_state["qa_cache"][cache_key] = (retrieved, ans)
        
            # Anchor target for auto-scroll
            st.markdown("<div id='answer-target'></div>", unsafe_allow_html=True)
            _display_answer_card(ans['answer'])
            # Trigger scroll once if requested
            if st.session_state.get("auto_scroll_answer"):
                components.html("""
                <script>
                const el = document.getElementById('answer-target');
                if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
                </script>
                """, height=0)
                st.session_state["auto_scroll_answer"] = False
        
            with st.expander("View All Retrieved Context"):
                for idx, c in enumerate(retrieved):
                    speaker = c.get("speaker") or "Unknown"
                    role = c.get("role")
                    section = c.get("section") or "?"
                    page = c.get("start_page") or "?"
                    score = c.get("score", 0.0)
                    header = f"Section: {section} | Page: {page} | Speaker: {speaker}"
                    if role:
                        header += f" · Role: {role.title()}"
                    header += f" | Score: {score:.3f}"
                    with st.expander(header, expanded=False):
                        st.text_area("Transcript Text",  value=c.get("text", ""), height=150, max_chars=None, key=f"ctx_{idx}", label_visibility="hidden")
