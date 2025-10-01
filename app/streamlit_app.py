import streamlit as st
import os
from scripts.pipeline import process_transcript
from scripts.rag_query import query_index, generate_answer
import warnings
import streamlit.components.v1 as components
import markdown 
warnings.filterwarnings("ignore")

st.set_page_config(page_title="📄 Transcript Assistant", layout="wide")
st.title("📄 Transcript Assistant")

# ---------- Initialize Session State ----------
if "docs" not in st.session_state:
    st.session_state["docs"] = []  # [{id, name, status: Processed|Error, data}]
if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = None
if "qa_cache" not in st.session_state:
    st.session_state["qa_cache"] = {}
if "focus_summary" not in st.session_state:
    st.session_state["focus_summary"] = False
if "auto_scroll_answer" not in st.session_state:
    st.session_state["auto_scroll_answer"] = False


# Cards
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
    # Convert Markdown to HTML
    html_content = markdown.markdown(ans_text, extensions=['extra', 'nl2br'])
    
    # Wrap in styled div
    st.markdown(
        f"<div style='background:#effaf1; color:#0b4d1a; padding:16px; "
        f"border-radius:12px; border:1px solid #cde9d6; word-wrap:break-word;'>"
        f"{html_content}</div>",
        unsafe_allow_html=True
    )


# ---------- Utility ----------
def _get_selected_data():
    doc_id = st.session_state.get("selected_doc_id")
    for d in st.session_state["docs"]:
        if d.get("id") == doc_id:
            return d
    return None

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

# ---------------- Upload Tab ----------------
with upload_tab:
    st.subheader("Upload a PDF Transcript")
    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"], key="upload_tab")
    if uploaded_file is not None:
        with st.spinner("Processing PDF..."):
            try:
                data = process_transcript(uploaded_file, chunk_size=500, overlap=50)
                doc_id = f"local::{uploaded_file.name}"
                # Update or insert
                found = None
                for d in st.session_state["docs"]:
                    if d.get("id") == doc_id:
                        found = d
                        break
                if found:
                    found.update({"name": uploaded_file.name, "status": "Processed", "data": data})
                else:
                    st.session_state["docs"].append({
                        "id": doc_id,
                        "name": uploaded_file.name,
                        "status": "Processed",
                        "data": data
                    })
                st.session_state["selected_doc_id"] = doc_id
                st.session_state["focus_summary"] = True
                st.success("Processing complete. Summary is now available.")
            except Exception as e:
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

        with tab3:
            items = data.get("topics_items", {}).get(section_name, [])
            selected = []
            for idx, item in enumerate(items):
                key = f"sel_{section_name}_{idx}"
                if st.checkbox(item.get("topic", f"Topic {idx+1}"), key=key):
                    selected.append(item)
            if st.button("Generate Summary", key="gen_sum_opening"):
                if not selected:
                    st.warning("Select at least one topic.")
                else:
                    formatted_summary = ""
                    for it in selected:
                        summary = it.get("summary", "")
                        paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
                        for para in paragraphs:
                            formatted_summary += f"{para}\n\n\n\n"
                    _display_answer_card(formatted_summary.strip())

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

        with tab3:
            items = data.get("topics_items", {}).get(section_name, [])
            selected = []
            for idx, item in enumerate(items):
                key = f"sel_{section_name}_{idx}"
                if st.checkbox(item.get("topic", f"Topic {idx+1}"), key=key):
                    selected.append(item)
            if st.button("Generate Summary", key="gen_sum_qa"):
                if not selected:
                    st.warning("Select at least one topic.")
                else:
                    formatted_summary = ""
                    for it in selected:
                        summary = it.get("summary", "")
                        paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
                        for para in paragraphs:
                            formatted_summary += f"{para}\n\n\n\n"
                    _display_answer_card(formatted_summary.strip())

# ---------------- Chat Assistant Tab ----------------
with chat_tab:
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
                    st.session_state["chat_input"] = q
                    st.session_state["auto_scroll_answer"] = True
                    st.rerun()
        question = st.text_input("Ask a question", key="chat_input")
        if question:
            cache_key = f"{data.get('doc_id')}::{question.strip().lower()}"
            if cache_key in st.session_state["qa_cache"]:
                retrieved, ans = st.session_state["qa_cache"][cache_key]
            else:
                with st.spinner("Retrieving context and generating answer..."):
                    pool = data["chunks"]
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
